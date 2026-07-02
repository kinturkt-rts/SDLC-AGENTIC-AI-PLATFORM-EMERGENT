# Deploy shared GitLab MCP (jmrplens HTTP) on ECS Fargate + ALB.
# CloudFront + AgentCore Gateway: see deploy/gitlab-mcp-server/README.md
#
# Prereqs: aws sso login --profile "Juno Developers", ECR image pushed (push-gitlab-mcp-ecr.ps1)
#
# Usage (from backend/):
#   .\scripts\deploy-gitlab-mcp-ecs.ps1
#   .\scripts\deploy-gitlab-mcp-ecs.ps1 -WhatIf
param(
    [string] $Region = "us-east-2",
    [string] $Profile = "Juno Developers",
    [string] $AccountId = "061836593297",
    [string] $Cluster = "sdlc-agentic-ai",
    [string] $ServiceName = "gitlab-mcp-server",
    [string] $TaskFamily = "gitlab-mcp-server",
    [string] $Repository = "bedrock-agentcore-gitlab_agent",
    [string] $ImageTag = "gitlab_mcp",
    [string] $VpcId = "vpc-036155f359e2e940c",
    [string[]] $SubnetIds = @(
        "subnet-044c04012037ca457",
        "subnet-07651619f77b51d7f",
        "subnet-0c0e7c749de659e32"
    ),
    [string] $AlbName = "gitlab-mcp-alb",
    [string] $TargetGroupName = "gitlab-mcp-tg",
    [string] $SgTaskName = "mcp-allow-sg-group",
    [string] $SgAlbName = "mcp-alb-sg-1",
    [string] $SgServiceName = "mcp-sg-allow-8080",
    [int] $DesiredCount = 1,
    [switch] $WhatIf
)

$ErrorActionPreference = "Stop"
$env:AWS_PROFILE = $Profile
$BackendRoot = Split-Path $PSScriptRoot -Parent
$ImageUri = "$AccountId.dkr.ecr.$Region.amazonaws.com/${Repository}:$ImageTag"
$ExecutionRoleName = "ecsTaskExecutionRole"

function Invoke-Aws([string[]] $Args) {
    if ($WhatIf) {
        Write-Host "[WhatIf] aws $($Args -join ' ')" -ForegroundColor DarkGray
        return $null
    }
    return aws @Args | ConvertFrom-Json
}

function Get-OrCreateExecutionRole {
    try {
        aws iam get-role --role-name $ExecutionRoleName --profile $Profile 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Using existing IAM role $ExecutionRoleName" -ForegroundColor Green
            return "arn:aws:iam::${AccountId}:role/$ExecutionRoleName"
        }
    } catch { }

    Write-Host "Creating IAM role $ExecutionRoleName ..." -ForegroundColor Cyan
    if ($WhatIf) {
        return "arn:aws:iam::${AccountId}:role/$ExecutionRoleName"
    }

    $trustFile = Join-Path $BackendRoot "deploy\gitlab-mcp-server\ecs-trust-policy.json"
    aws iam create-role `
        --role-name $ExecutionRoleName `
        --assume-role-policy-document "file://$($trustFile.Replace('\', '/'))" `
        --profile $Profile | Out-Null

    aws iam attach-role-policy `
        --role-name $ExecutionRoleName `
        --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" `
        --profile $Profile | Out-Null

    Start-Sleep -Seconds 10
    return "arn:aws:iam::${AccountId}:role/$ExecutionRoleName"
}

function Get-OrCreateSecurityGroup {
    param(
        [string] $Name,
        [string] $Description
    )

    $existing = aws ec2 describe-security-groups `
        --region $Region `
        --filters "Name=group-name,Values=$Name" "Name=vpc-id,Values=$VpcId" `
        --query "SecurityGroups[0].GroupId" `
        --output text 2>$null

    if ($existing -and $existing -ne "None") {
        Write-Host "SG $Name exists: $existing" -ForegroundColor Green
        return $existing
    }

    Write-Host "Creating SG $Name ..." -ForegroundColor Cyan
    if ($WhatIf) { return "sg-whatif" }

    $sgId = aws ec2 create-security-group `
        --group-name $Name `
        --description $Description `
        --vpc-id $VpcId `
        --region $Region `
        --query "GroupId" `
        --output text
    return $sgId
}

Write-Host "Checking AWS identity..." -ForegroundColor Cyan
aws sts get-caller-identity --region $Region | Out-Null

Write-Host "Ensuring CloudWatch log group /ecs/gitlab-mcp-server ..." -ForegroundColor Cyan
if (-not $WhatIf) {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    aws logs create-log-group --log-group-name /ecs/gitlab-mcp-server --region $Region 2>&1 | Out-Null
    $ErrorActionPreference = $prevEap
}

Write-Host "Ensuring ECS cluster $Cluster ..." -ForegroundColor Cyan
if (-not $WhatIf) {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    aws ecs create-cluster --cluster-name $Cluster --region $Region 2>&1 | Out-Null
    $ErrorActionPreference = $prevEap
}

$executionRoleArn = Get-OrCreateExecutionRole

$sgAlb = Get-OrCreateSecurityGroup -Name $SgAlbName -Description "ALB for GitLab MCP"
$sgTask = Get-OrCreateSecurityGroup -Name $SgTaskName -Description "GitLab MCP Fargate tasks"
$sgService = Get-OrCreateSecurityGroup -Name $SgServiceName -Description "GitLab MCP ECS service"

if (-not $WhatIf) {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    # ALB: HTTP from internet (CloudFront reaches ALB over HTTP)
    aws ec2 authorize-security-group-ingress `
        --group-id $sgAlb --protocol tcp --port 80 --cidr 0.0.0.0/0 --region $Region 2>&1 | Out-Null

    # Tasks: 8080 from ALB SG and service SG
    aws ec2 authorize-security-group-ingress `
        --group-id $sgTask --protocol tcp --port 8080 --source-group $sgAlb --region $Region 2>&1 | Out-Null
    aws ec2 authorize-security-group-ingress `
        --group-id $sgTask --protocol tcp --port 8080 --source-group $sgService --region $Region 2>&1 | Out-Null

  $ErrorActionPreference = $prevEap
}

Write-Host "Registering task definition $TaskFamily ..." -ForegroundColor Cyan
$taskDefTemplate = Join-Path $BackendRoot "deploy\gitlab-mcp-server\task-definition.json"
$taskDefJson = (Get-Content $taskDefTemplate -Raw) `
    -replace "EXECUTION_ROLE_ARN", $executionRoleArn `
    -replace "IMAGE_URI", $ImageUri

if ($WhatIf) {
    Write-Host "[WhatIf] register-task-definition ..." -ForegroundColor DarkGray
    $taskDefArn = "arn:aws:ecs:${Region}:${AccountId}:task-definition/${TaskFamily}:1"
} else {
    $taskDefFile = Join-Path $env:TEMP "gitlab-mcp-task-def.json"
    [System.IO.File]::WriteAllText($taskDefFile, $taskDefJson)
    $taskDefArn = aws ecs register-task-definition `
        --region $Region `
        --cli-input-json "file://$($taskDefFile.Replace('\', '/'))" `
        --query "taskDefinition.taskDefinitionArn" `
        --output text
    if (-not $taskDefArn) { throw "Failed to register task definition" }
    Write-Host "Task definition: $taskDefArn" -ForegroundColor Green
}

Write-Host "Creating ALB $AlbName ..." -ForegroundColor Cyan
$albArn = $null
$albDns = $null
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$existingAlb = aws elbv2 describe-load-balancers `
    --region $Region `
    --names $AlbName `
    --query "LoadBalancers[0].LoadBalancerArn" `
    --output text 2>&1
$ErrorActionPreference = $prevEap
if ($existingAlb -match "LoadBalancerNotFound") { $existingAlb = $null }

if ($existingAlb -and $existingAlb -ne "None") {
    $albArn = $existingAlb
    $albDns = aws elbv2 describe-load-balancers --region $Region --load-balancer-arns $albArn `
        --query "LoadBalancers[0].DNSName" --output text
    Write-Host "ALB exists: $albDns" -ForegroundColor Green
} elseif (-not $WhatIf) {
    $albArn = aws elbv2 create-load-balancer `
        --name $AlbName `
        --type application `
        --scheme internet-facing `
        --ip-address-type ipv4 `
        --subnets $SubnetIds `
        --security-groups $sgAlb `
        --region $Region `
        --query "LoadBalancers[0].LoadBalancerArn" `
        --output text
    $albDns = aws elbv2 describe-load-balancers --region $Region --load-balancer-arns $albArn `
        --query "LoadBalancers[0].DNSName" --output text
    Write-Host "ALB created: $albDns" -ForegroundColor Green
} else {
    $albDns = "$AlbName.$Region.elb.amazonaws.com"
}

$tgArn = $null
$ErrorActionPreference = "Continue"
$existingTg = aws elbv2 describe-target-groups `
    --region $Region `
    --names $TargetGroupName `
    --query "TargetGroups[0].TargetGroupArn" `
    --output text 2>&1
$ErrorActionPreference = "Stop"
if ($existingTg -match "TargetGroupNotFound") { $existingTg = $null }

if ($existingTg -and $existingTg -ne "None") {
    $tgArn = $existingTg
    Write-Host "Target group exists: $tgArn" -ForegroundColor Green
} elseif (-not $WhatIf) {
    $tgArn = aws elbv2 create-target-group `
        --name $TargetGroupName `
        --protocol HTTP `
        --port 8080 `
        --vpc-id $VpcId `
        --target-type ip `
        --health-check-protocol HTTP `
        --health-check-path "/mcp" `
        --health-check-port "8080" `
        --matcher HttpCode=200-499 `
        --region $Region `
        --query "TargetGroups[0].TargetGroupArn" `
        --output text
    Write-Host "Target group created: $tgArn" -ForegroundColor Green
}

if ($albArn -and $tgArn -and -not $WhatIf) {
    $listeners = aws elbv2 describe-listeners --region $Region --load-balancer-arn $albArn `
        --query "Listeners[?Port==``80``].ListenerArn" --output text 2>$null
    if (-not $listeners) {
        aws elbv2 create-listener `
            --load-balancer-arn $albArn `
            --protocol HTTP `
            --port 80 `
            --default-actions "Type=forward,TargetGroupArn=$tgArn" `
            --region $Region | Out-Null
        Write-Host "ALB listener :80 -> target group" -ForegroundColor Green
    }
}

Write-Host "Creating/updating ECS service $ServiceName ..." -ForegroundColor Cyan
$existingService = aws ecs describe-services `
    --cluster $Cluster `
    --services $ServiceName `
    --region $Region `
    --query "services[?status!='INACTIVE'].serviceArn" `
    --output text 2>$null

$networkConfig = "awsvpcConfiguration={subnets=[$($SubnetIds -join ',')],securityGroups=[$sgTask,$sgService],assignPublicIp=ENABLED}"

if ($existingService -and $existingService -ne "None") {
    if (-not $WhatIf) {
        aws ecs update-service `
            --cluster $Cluster `
            --service $ServiceName `
            --task-definition $TaskFamily `
            --desired-count $DesiredCount `
            --force-new-deployment `
            --region $Region | Out-Null
        Write-Host "ECS service updated" -ForegroundColor Green
    }
} elseif (-not $WhatIf) {
    aws ecs create-service `
        --cluster $Cluster `
        --service-name $ServiceName `
        --task-definition $TaskFamily `
        --desired-count $DesiredCount `
        --launch-type FARGATE `
        --network-configuration $networkConfig `
        --load-balancers "targetGroupArn=$tgArn,containerName=gitlab-mcp-server,containerPort=8080" `
        --health-check-grace-period-seconds 120 `
        --region $Region | Out-Null
    Write-Host "ECS service created" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Next steps ===" -ForegroundColor Cyan
Write-Host "1. Wait for ECS tasks healthy in target group (ECS console -> cluster $Cluster)"
Write-Host "2. Create CloudFront distribution (see deploy/gitlab-mcp-server/README.md)"
Write-Host "   Origin: ALB $albDns (HTTP only)"
Write-Host "3. Update config/agentcore/gitlab-mcp-endpoints.json (albDnsName, directMcpUrl)"
Write-Host "4. Redeploy gitlab-agent: .\scripts\deploy-agentcore-agents.ps1 -Agents gitlab_agent -SkipConfigure"
Write-Host ""
Write-Host "ALB DNS (gitlab-agent publish / GITLAB_MCP_HTTP_DIRECT_URL):" -ForegroundColor Yellow
Write-Host "  http://$albDns/mcp"
