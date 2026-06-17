"""ORM schema helpers — schema is set on ``Base.metadata`` in ``app.database``."""


def orm_table_args() -> dict[str, str]:
    """Kept for model compatibility; schema lives on ``Base.metadata`` for FK resolution."""
    return {}
