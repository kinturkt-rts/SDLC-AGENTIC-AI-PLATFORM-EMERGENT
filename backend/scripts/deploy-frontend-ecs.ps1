# Deploy SDLC control-plane frontend on ECS Fargate + ALB.
#
# Prereqs:
#   aws sso login --profile eks-admin-user
#   .\scripts\push-frontend-ecr.ps1
#   IAM task role sdlc-control-plane-task (S3 artifact bucket, CloudWatch Logs, bedrock-agentcore:InvokeAgentRuntime)
#
# Usage (from backend/):
#   .\scripts\deploy-frontend-ecs.ps1 -WhatIf
#   .\scripts\deploy-frontend-ecs.ps1

param(
    [string] $Region = "us-east-2",
    [string] $Profile = "eks-admin-user",
    [string] $AccountId = "061836593297",
    [string] $Cluster = "sdlc-agentic-ai",
    [string] $ServiceName = "sdlc-control-plane",
    [string] $TaskFamily = "sdlc-control-plane",
    [string] $Repository = "sdlc-control-plane",
    [string] $ImageTag = "latest",
    [string] $VpcId = "vpc-036155f359e2e940c",
    [string[]] $SubnetIds = @(
        "subnet-044c04012037ca457",
        "subnet-07651619f77b51d7f",
        "subnet-0c0e7c749de659e32"
    ),
    [string] $AlbName = "sdlc-control-plane-alb",
    [string] $TargetGroupName = "sdlc-control-plane-tg",
    [int] $DesiredCount = 1,
    [switch] $WhatIf
)

$ErrorActionPreference = "Stop"
$env:AWS_PROFILE = $Profile
$BackendRoot = Split-Path $PSScriptRoot -Parent
$MonorepoRoot = Split-Path $BackendRoot -Parent
$ImageUri = "$AccountId.dkr.ecr.$Region.amazonaws.com/${Repository}:$ImageTag"
$ExecutionRoleName = "ecsTaskExecutionRole"
$TaskRoleName = "sdlc-control-plane-task"
$GitlabPatSecretName = "sdlc/control-plane/gitlab-pat"

function Import-DotenvKeys([string[]] $Keys) {
    foreach ($path in @(
        (Join-Path $MonorepoRoot ".env.local"),
        (Join-Path $BackendRoot ".env.local"),
        (Join-Path $MonorepoRoot ".env"),
        (Join-Path $BackendRoot ".env")
    )) {
        if (-not (Test-Path $path)) { continue }
        Get-Content $path | ForEach-Object {
            $line = $_.Trim()
            if ($line -match '^\s*#' -or -not $line) { return }
            if ($line -match '^\s*([^=]+)=(.*)$') {
                $key = $matches[1].Trim()
                $val = $matches[2].Trim().Trim('"').Trim("'")
                if ($val -and ($Keys -contains $key) -and -not [Environment]::GetEnvironmentVariable($key)) {
                    [Environment]::SetEnvironmentVariable($key, $val, "Process")
                }
            }
        }
    }
}

function Ensure-GitlabPatSecret {
    Import-DotenvKeys @("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_URL", "GITLAB_TOKEN")
    $pat = $env:GITLAB_PERSONAL_ACCESS_TOKEN
    if (-not $pat) { $pat = $env:GITLAB_TOKEN }
    if (-not $pat) {
        throw "GITLAB_PERSONAL_ACCESS_TOKEN not set. Add it to .env.local before deploying control-plane (needed for Deploy/GitLab sync)."
    }

    $secretArn = $null
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $describedRaw = aws secretsmanager describe-secret `
        --secret-id $GitlabPatSecretName `
        --region $Region `
        --profile $Profile `
        --output json 2>$null
    $describeOk = ($LASTEXITCODE -eq 0 -and $describedRaw)
    $ErrorActionPreference = $prevEap

    if ($describeOk) {
        $secretArn = ($describedRaw | ConvertFrom-Json).ARN
        Write-Host "Updating Secrets Manager $GitlabPatSecretName ..." -ForegroundColor Cyan
        if (-not $WhatIf) {
            $ErrorActionPreference = "Continue"
            aws secretsmanager put-secret-value `
                --secret-id $GitlabPatSecretName `
                --secret-string $pat `
                --region $Region `
                --profile $Profile | Out-Null
            $putOk = ($LASTEXITCODE -eq 0)
            $ErrorActionPreference = $prevEap
            if (-not $putOk) { throw "put-secret-value failed for $GitlabPatSecretName" }
        }
    } else {
        Write-Host "Creating Secrets Manager $GitlabPatSecretName ..." -ForegroundColor Cyan
        if ($WhatIf) {
            return "arn:aws:secretsmanager:${Region}:${AccountId}:secret:${GitlabPatSecretName}-XXXXXX"
        }
        $ErrorActionPreference = "Continue"
        $createdRaw = aws secretsmanager create-secret `
            --name $GitlabPatSecretName `
            --description "GitLab PAT for SDLC control-plane Deploy status sync" `
            --secret-string $pat `
            --region $Region `
            --profile $Profile `
            --output json 2>&1
        $createOk = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = $prevEap
        if (-not $createOk) {
            throw "create-secret failed for $GitlabPatSecretName : $createdRaw"
        }
        $created = $createdRaw | ConvertFrom-Json
        if (-not $created.ARN) {
            throw "create-secret failed for $GitlabPatSecretName (no ARN)"
        }
        $secretArn = $created.ARN
    }

    # Execution role must read the secret at task start (ECS injects env from secrets).
    $policyDoc = @{
        Version = "2012-10-17"
        Statement = @(
            @{
                Sid      = "ControlPlaneGitlabPat"
                Effect   = "Allow"
                Action   = @("secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret")
                Resource = @($secretArn, "arn:aws:secretsmanager:${Region}:${AccountId}:secret:sdlc/control-plane/gitlab-pat*")
            }
        )
    } | ConvertTo-Json -Depth 6 -Compress
    $policyFile = Join-Path $env:TEMP "sdlc-cp-gitlab-pat-exec-policy.json"
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($policyFile, $policyDoc, $utf8NoBom)
    if (-not $WhatIf) {
        Write-Host "Attaching gitlab-pat read policy to $ExecutionRoleName ..." -ForegroundColor Cyan
        aws iam put-role-policy `
            --role-name $ExecutionRoleName `
            --policy-name sdlc-control-plane-gitlab-pat `
            --policy-document "file://$($policyFile.Replace('\', '/'))" `
            --profile $Profile | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Failed to attach gitlab-pat policy to $ExecutionRoleName" }
    }

    return $secretArn
}

function Invoke-Aws([string[]] $AwsArgs) {
    if ($WhatIf) {
        Write-Host "[WhatIf] aws $($AwsArgs -join ' ')" -ForegroundColor DarkGray
        return $null
    }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = aws @AwsArgs
        if ($LASTEXITCODE -ne 0) { throw ($out | Out-String) }
        if ($out) { return $out | ConvertFrom-Json }
        return $null
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Get-OrCreateLogGroup {
    $name = "/ecs/sdlc-control-plane"
    if ($WhatIf) { return }
    $existing = aws logs describe-log-groups --log-group-name-prefix $name --region $Region --profile $Profile 2>$null | ConvertFrom-Json
    if ($existing.logGroups | Where-Object { $_.logGroupName -eq $name }) {
        return
    }
    aws logs create-log-group --log-group-name $name --region $Region --profile $Profile 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to create log group $name" }
}

function Get-OrCreateSecurityGroup {
    param([string] $Name, [string] $Description)
    $existing = aws ec2 describe-security-groups --filters "Name=group-name,Values=$Name" "Name=vpc-id,Values=$VpcId" --region $Region --profile $Profile 2>$null | ConvertFrom-Json
    if ($existing.SecurityGroups.Count -gt 0) {
        return $existing.SecurityGroups[0].GroupId
    }
    if ($WhatIf) { return "sg-whatif" }
    $created = aws ec2 create-security-group --group-name $Name --description $Description --vpc-id $VpcId --region $Region --profile $Profile | ConvertFrom-Json
    return $created.GroupId
}

Write-Host "Ensuring CloudWatch log group /ecs/sdlc-control-plane ..." -ForegroundColor Cyan
Get-OrCreateLogGroup

Write-Host "Checking IAM task role $TaskRoleName (create manually if missing) ..." -ForegroundColor Cyan
if (-not $WhatIf) {
    aws iam get-role --role-name $TaskRoleName --profile $Profile 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning @"
Task role '$TaskRoleName' not found. Create it with policies for:
  - s3:GetObject, s3:PutObject, s3:ListBucket on artifact bucket
  - logs:FilterLogEvents on /aws/bedrock-agentcore/*
  - bedrock-agentcore:InvokeAgentRuntime
Then re-run this script.
"@
        exit 1
    }
}

$gitlabPatArn = Ensure-GitlabPatSecret
$gitlabUrl = if ($env:GITLAB_URL) { $env:GITLAB_URL.Trim().TrimEnd('/') } else { "https://code.junodev.net" }

$taskDefTemplate = Join-Path $BackendRoot "deploy\control-plane-frontend\task-definition.json"
$taskDefRaw = Get-Content $taskDefTemplate -Raw
$taskDefRaw = $taskDefRaw.Replace(
    "061836593297.dkr.ecr.us-east-2.amazonaws.com/sdlc-control-plane:latest",
    $ImageUri
)
# Prefer full secret ARN (includes random suffix) so ECS can resolve GetSecretValue.
$taskDefRaw = $taskDefRaw.Replace(
    "arn:aws:secretsmanager:us-east-2:061836593297:secret:sdlc/control-plane/gitlab-pat",
    $gitlabPatArn
)
# Keep GITLAB_URL in sync with .env.local when present.
$taskDefRaw = [regex]::Replace(
    $taskDefRaw,
    '"name":\s*"GITLAB_URL",\s*"value":\s*"[^"]*"',
    ('"name": "GITLAB_URL", "value": "' + $gitlabUrl + '"')
)
$taskDefFile = Join-Path $env:TEMP "sdlc-control-plane-task-def.json"
# AWS CLI rejects UTF-8 BOM in --cli-input-json files (PowerShell 5 default utf8 adds BOM).
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($taskDefFile, $taskDefRaw, $utf8NoBom)

Write-Host "Registering task definition $TaskFamily ..." -ForegroundColor Cyan
$reg = Invoke-Aws @("ecs", "register-task-definition", "--cli-input-json", "file://$($taskDefFile.Replace('\', '/'))", "--region", $Region, "--profile", $Profile)
$taskDefArn = $reg.taskDefinition.taskDefinitionArn

$albSg = Get-OrCreateSecurityGroup -Name "sdlc-cp-alb-sg" -Description "ALB for SDLC control plane"
$taskSg = Get-OrCreateSecurityGroup -Name "sdlc-cp-task-sg" -Description "ECS tasks for SDLC control plane"

if (-not $WhatIf) {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    aws ec2 authorize-security-group-ingress --group-id $albSg --protocol tcp --port 80 --cidr 0.0.0.0/0 --region $Region --profile $Profile 2>$null | Out-Null
    aws ec2 authorize-security-group-ingress --group-id $taskSg --protocol tcp --port 3000 --source-group $albSg --region $Region --profile $Profile 2>$null | Out-Null
    $ErrorActionPreference = $prevEap
}

Write-Host "Ensuring ALB $AlbName ..." -ForegroundColor Cyan
$alb = $null
try {
    $alb = aws elbv2 describe-load-balancers --names $AlbName --region $Region --profile $Profile | ConvertFrom-Json
} catch { }
if (-not $alb -or $alb.LoadBalancers.Count -eq 0) {
    if ($WhatIf) {
        Write-Host "[WhatIf] Would create ALB $AlbName" -ForegroundColor DarkGray
    } else {
        $alb = aws elbv2 create-load-balancer `
            --name $AlbName `
            --subnets $SubnetIds `
            --security-groups $albSg `
            --scheme internet-facing `
            --type application `
            --region $Region `
            --profile $Profile | ConvertFrom-Json
    }
}
$albArn = $alb.LoadBalancers[0].LoadBalancerArn
$albDns = $alb.LoadBalancers[0].DNSName

Write-Host "Ensuring target group $TargetGroupName ..." -ForegroundColor Cyan
$tg = $null
try {
    $tg = aws elbv2 describe-target-groups --names $TargetGroupName --region $Region --profile $Profile | ConvertFrom-Json
} catch { }
if (-not $tg -or $tg.TargetGroups.Count -eq 0) {
    if ($WhatIf) {
        Write-Host "[WhatIf] Would create target group" -ForegroundColor DarkGray
    } else {
        $tg = aws elbv2 create-target-group `
            --name $TargetGroupName `
            --protocol HTTP `
            --port 3000 `
            --vpc-id $VpcId `
            --target-type ip `
            --health-check-path "/api/health" `
            --region $Region `
            --profile $Profile | ConvertFrom-Json
    }
}
$tgArn = $tg.TargetGroups[0].TargetGroupArn

if (-not $WhatIf) {
    $listeners = aws elbv2 describe-listeners --load-balancer-arn $albArn --region $Region --profile $Profile | ConvertFrom-Json
    if ($listeners.Listeners.Count -eq 0) {
        aws elbv2 create-listener `
            --load-balancer-arn $albArn `
            --protocol HTTP `
            --port 80 `
            --default-actions "Type=forward,TargetGroupArn=$tgArn" `
            --region $Region `
            --profile $Profile | Out-Null
    }
}

Write-Host "Ensuring ECS service $ServiceName on cluster $Cluster ..." -ForegroundColor Cyan
$svc = $null
try {
    $svc = aws ecs describe-services --cluster $Cluster --services $ServiceName --region $Region --profile $Profile | ConvertFrom-Json
} catch { }
$exists = $svc -and $svc.services.Count -gt 0 -and $svc.services[0].status -ne "INACTIVE"

if ($exists) {
    if ($WhatIf) {
        Write-Host "[WhatIf] Would update service $ServiceName" -ForegroundColor DarkGray
    } else {
        aws ecs update-service `
            --cluster $Cluster `
            --service $ServiceName `
            --task-definition $taskDefArn `
            --desired-count $DesiredCount `
            --force-new-deployment `
            --region $Region `
            --profile $Profile | Out-Null
    }
} else {
    if ($WhatIf) {
        Write-Host "[WhatIf] Would create service $ServiceName" -ForegroundColor DarkGray
    } else {
        aws ecs create-service `
            --cluster $Cluster `
            --service-name $ServiceName `
            --task-definition $taskDefArn `
            --desired-count $DesiredCount `
            --launch-type FARGATE `
            --network-configuration "awsvpcConfiguration={subnets=[$($SubnetIds -join ',')],securityGroups=[$taskSg],assignPublicIp=ENABLED}" `
            --load-balancers "targetGroupArn=$tgArn,containerName=sdlc-control-plane,containerPort=3000" `
            --region $Region `
            --profile $Profile | Out-Null
    }
}

Write-Host ""
Write-Host "Control plane URL (after tasks healthy): http://$albDns" -ForegroundColor Green
Write-Host "Health: http://$albDns/api/health" -ForegroundColor DarkGray
