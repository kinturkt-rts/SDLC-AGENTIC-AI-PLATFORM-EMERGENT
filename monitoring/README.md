# Monitoring (planned)

Grafana dashboards and alert rules for deployed `target-apps/` services and agent runtime health.

**Not scaffolded yet.** When added, expect:

- `dashboards/` — JSON or provisioning YAML for Grafana
- `alerts/` — alert rule definitions (latency, error rate, RDS, Bedrock throttling)

Until then, use CloudWatch (see user MCP config) or platform logs from agent CLI runs.
