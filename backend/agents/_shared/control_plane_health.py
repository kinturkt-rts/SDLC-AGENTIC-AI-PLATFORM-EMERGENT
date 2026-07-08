"""Control-plane UI pings AgentCore with a fixed health-check phrase."""


def is_control_plane_health_check(text: str) -> bool:
    return text.strip().lower().startswith("control-plane health check")
