"""Customer router — CRUD for customers and their service addresses."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser, DispatcherUser
from app.models.customer import Customer, ServiceAddress
from schemas.customer import CustomerCreate, CustomerOut, CustomerUpdate

router = APIRouter(tags=["customers"])


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(
    body: CustomerCreate,
    current_user: DispatcherUser,
    db: Session = Depends(get_db),
) -> CustomerOut:
    """Create a customer with service addresses. Dispatcher only."""
    if not body.service_addresses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one service address is required",
        )
    customer = Customer(
        full_name=body.full_name,
        phone=body.phone,
        email=body.email,
    )
    for addr in body.service_addresses:
        customer.service_addresses.append(
            ServiceAddress(
                street=addr.street,
                city=addr.city,
                state=addr.state,
                postal_code=addr.postal_code,
            )
        )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer  # type: ignore[return-value]


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CustomerOut:
    """Get a customer by ID. Dispatcher + Owner."""
    if current_user.role not in ("dispatcher", "owner"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer  # type: ignore[return-value]


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: str,
    body: CustomerUpdate,
    current_user: DispatcherUser,
    db: Session = Depends(get_db),
) -> CustomerOut:
    """Partially update a customer. Dispatcher only."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(customer, k, v)
    db.commit()
    db.refresh(customer)
    return customer  # type: ignore[return-value]
