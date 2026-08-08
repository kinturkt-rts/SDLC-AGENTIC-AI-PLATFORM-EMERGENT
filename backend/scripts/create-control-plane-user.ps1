# Create a Cognito user for the control-plane UI (admin-only pool).

# Usage:
#   aws sso login --profile eks-admin-user
#   .\scripts\create-control-plane-user.ps1 -Email you@company.com
#   .\scripts\create-control-plane-user.ps1 -Email you@company.com -Password 'YourPass123!'

param(
    [Parameter(Mandatory = $true)] [string] $Email,
    [string] $Password = "",
    [string] $UserPoolId = $env:COGNITO_USER_POOL_ID,
    [string] $Region = "us-east-2",
    [string] $Profile = "eks-admin-user"
)

$ErrorActionPreference = "Stop"
$env:AWS_PROFILE = $Profile

if (-not $UserPoolId) {
    $tfDir = Join-Path (Split-Path $PSScriptRoot -Parent) "infrastructure\environments\dev\control-plane-auth"
    if (Test-Path $tfDir) {
        Push-Location $tfDir
        try {
            $prevEap = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            $UserPoolId = (terraform output -raw user_pool_id 2>$null)
            if ($LASTEXITCODE -ne 0) { $UserPoolId = "" }
            $ErrorActionPreference = $prevEap
        } finally {
            Pop-Location
        }
    }
}

if (-not $UserPoolId) {
    $taskDef = Join-Path (Split-Path $PSScriptRoot -Parent) "deploy\control-plane-frontend\task-definition.json"
    if (Test-Path $taskDef) {
        $match = Select-String -Path $taskDef -Pattern '"COGNITO_USER_POOL_ID",\s*"value":\s*"([^"]+)"'
        if ($match) { $UserPoolId = $match.Matches[0].Groups[1].Value }
    }
}
if (-not $UserPoolId) {
    throw "COGNITO_USER_POOL_ID not set. Pass -UserPoolId, set the env var, or apply control-plane-auth Terraform."
}

if (-not $Password) {
    $Password = "Welcome-" + ([guid]::NewGuid().ToString("N").Substring(0, 8)) + "aA1"
}

Write-Host "Ensuring Cognito user $Email in pool $UserPoolId ..." -ForegroundColor Cyan

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
aws cognito-idp admin-create-user `
    --user-pool-id $UserPoolId `
    --username $Email `
    --user-attributes "Name=email,Value=$Email" "Name=email_verified,Value=true" `
    --temporary-password $Password `
    --message-action SUPPRESS `
    --region $Region `
    --profile $Profile 2>$null | Out-Null
# Non-zero is OK when the user already exists — password set below is the real fix.
aws cognito-idp admin-set-user-password `
    --user-pool-id $UserPoolId `
    --username $Email `
    --password $Password `
    --permanent `
    --region $Region `
    --profile $Profile
$setCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap
if ($setCode -ne 0) { throw "admin-set-user-password failed" }

Write-Host "`nUser ready." -ForegroundColor Green
Write-Host "  Email:    $Email"
Write-Host "  Password: $Password" -ForegroundColor Yellow
Write-Host "  Sign in at the control-plane /login page."