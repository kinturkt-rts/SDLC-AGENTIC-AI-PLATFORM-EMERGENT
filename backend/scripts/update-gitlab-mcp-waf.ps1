# Exempt POST /mcp from AWSManagedRulesCommonRuleSet (GenericLFI_BODY blocks publish bodies).
# CloudFront distribution: d1cvmpnnohwpj8.cloudfront.net
#
# Usage (from backend/):
#   aws sso login --profile "Juno Developers"
#   .\scripts\update-gitlab-mcp-waf.ps1
#   .\scripts\update-gitlab-mcp-waf.ps1 -WhatIf
param(
    [string] $Profile = "Juno Developers",
    [string] $WebAclName = "CreatedByCloudFront-0a676d76",
    [string] $WebAclId = "0c9ad62c-c1ea-43b7-8390-781637eea7b9",
    [string] $Region = "us-east-1",
    [switch] $WhatIf
)

$ErrorActionPreference = "Stop"
$env:AWS_PROFILE = $Profile

Write-Host "Updating WAF Web ACL $WebAclName - CommonRuleSet scoped away from URI /mcp" -ForegroundColor Cyan

if ($WhatIf) {
    & python (Join-Path $PSScriptRoot "update_gitlab_mcp_waf.py") --what-if
    exit $LASTEXITCODE
}

& python (Join-Path $PSScriptRoot "update_gitlab_mcp_waf.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "CloudFront publish should use GITLAB_MCP_URL (see gitlab-mcp-endpoints.json)." -ForegroundColor Green
