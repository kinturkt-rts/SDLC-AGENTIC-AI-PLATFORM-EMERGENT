"""ORM model package — re-exports each table mapper for convenient imports."""

from app.models.category import Category
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.user import User, UserRole

__all__ = ["Category", "Product", "StockMovement", "User", "UserRole"]
