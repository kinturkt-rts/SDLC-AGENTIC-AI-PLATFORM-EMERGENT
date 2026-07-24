# Create a Cognito user for the control-plane UI (admin-only pool).
#
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
            $UserPoolId = (terraform output -raw user_pool_id 2>$null)
        } finally {
            Pop-Location
        }
    }
}
if (-not $UserPoolId) {
    throw "COGNITO_USER_POOL_ID not set. Apply control-plane-auth Terraform first, then re-run."
}

if (-not $Password) {
    # Cognito policy: min 10, upper, lower, number
    $Password = "Welcome-" + ([guid]::NewGuid().ToString("N").Substring(0, 8)) + "aA1"
}

Write-Host "Ensuring Cognito user $Email in pool $UserPoolId ..." -ForegroundColor Cyan

aws cognito-idp admin-create-user `
    --user-pool-id $UserPoolId `
    --username $Email `
    --user-attributes "Name=email,Value=$Email" "Name=email_verified,Value=true" `
    --temporary-password $Password `
    --message-action SUPPRESS `
    --region $Region `
    --profile $Profile 2>$null | Out-Null

aws cognito-idp admin-set-user-password `
    --user-pool-id $UserPoolId `
    --username $Email `
    --password $Password `
    --permanent `
    --region $Region `
    --profile $Profile
if ($LASTEXITCODE -ne 0) { throw "admin-set-user-password failed" }

Write-Host "`nUser ready." -ForegroundColor Green
Write-Host "  Email:    $Email"
Write-Host "  Password: $Password" -ForegroundColor Yellow
Write-Host "  Sign in at the control-plane /login page."
