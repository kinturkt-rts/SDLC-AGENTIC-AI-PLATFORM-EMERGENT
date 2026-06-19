"""ORM models package — import all models so Base.metadata sees them."""
from app.models.zone import Zone  # noqa: F401
from app.models.desk import Desk  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.booking import Booking  # noqa: F401
from app.models.blackout import Blackout  # noqa: F401
