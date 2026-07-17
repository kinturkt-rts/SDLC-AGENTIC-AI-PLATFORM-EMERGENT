"""ORM model registry — import all models so Base.metadata sees them."""
from app.models.customer import Customer  # noqa: F401
from app.models.technician import Technician  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.work_order import WorkOrder  # noqa: F401
from app.models.assignment import Assignment  # noqa: F401
from app.models.part_line_item import PartLineItem  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
