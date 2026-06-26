# PRD Output Directory

`product-agent` can generate a Product Requirements Document (PRD) in Markdown and save it here.

**Input:** any plain-text brief (notes, email, bullets) — the agent infers a full PM-style PRD with functional requirements (FR-*), non-functional requirements (NFR-*), goals, scope, risks, and open questions. You do not need to write FR/NFR in the source file.

## Defaults
- Output directory: `docs/PRD/`
- Env override: `PRODUCT_PRD_OUTPUT_DIR`

## CLI usage (PRD only)
```powershell
python agents/product-agent/product_agent.py `
  --input-file inputs/checkout.txt `
  --prd-name checkout
```

## CLI usage (minimal Jira test)
```powershell
python agents/product-agent/product_agent.py `
  --input-file inputs/checkout.txt `
  --prd-name checkout `
  --project ASAAP `
  --sprint 1 `
  --allow-writes `
  --create-minimal-jira
```
