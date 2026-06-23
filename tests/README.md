# Tests

Lean pytest suite for **shared pipeline infrastructure** — not full agent runs.
Agent behavior is verified by running agents directly (`python agents/<name>/*_agent.py`).

```bash
python -m pytest tests/ -q
```

| File | Covers |
|------|--------|
| `test_pipeline_context.py` | `targetApp` resolution, slugify, CLI context |
| `test_apply_sql_to_rds.py` | `scripts/apply_sql_to_rds.py` |
| `test_rds_env_schema.py` | `agents/_shared/rds_env.py` |
| `test_seed_credentials.py` | Seed SQL credential parsing |
| `test_verify_seed_bcrypt.py` | Bcrypt seed validation (`run-sdlc` gate) |
| `test_validate_rds_parity.py` | RDS parity (`scripts/verify_app_parity.py`) |
| `test_validate_ui_parity.py` | UI/API surface parity (`run-sdlc` local verify) |
| `test_delivery_profile.py` | Streamlit delivery profile detection |

Target-app tests: `target-apps/<service>/tests/`
