"""Items router for demo-api.

Exposes GET /items returning a JSON list with a single seed item.
"""

from fastapi import APIRouter

from schemas.items import Item

router = APIRouter(tags=["items"])


@router.get("/items", response_model=list[Item])
def list_items() -> list[Item]:
    """Return a list with one demo item."""
    return [Item(id=1, name="demo-item")]
