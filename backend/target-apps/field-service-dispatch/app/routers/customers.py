"""Customers router."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DbSession, DispatcherUser, DispatcherOrOwner
from app.models.customer import Customer
from schemas.customer import CustomerCreate, CustomerOut, CustomerUpdate

router = APIRouter()


@router.get("/api/v1/customers", response_model=list[CustomerOut])
def list_customers(
    current_user: DispatcherOrOwner,
    db: DbSession,
) -> list[CustomerOut]:
    """List all non-deleted customers."""
    rows = db.scalars(
        select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.full_name)
    ).all()
    return [CustomerOut.model_validate(r) for r in rows]


@router.post("/api/v1/customers", response_model=CustomerOut, status_code=201)
def create_customer(
    body: CustomerCreate,
    current_user: DispatcherUser,
    db: DbSession,
) -> CustomerOut:
    """Create a new customer (dispatcher only)."""
    customer = Customer(**body.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerOut.model_validate(customer)


@router.put("/api/v1/customers/{id}", response_model=CustomerOut)
def update_customer(
    id: str,
    body: CustomerUpdate,
    current_user: DispatcherUser,
    db: DbSession,
) -> CustomerOut:
    """Update customer fields."""
    customer = db.get(Customer, id)
    if not customer or customer.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Customer not found")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(customer, k, v)
    db.commit()
    db.refresh(customer)
    return CustomerOut.model_validate(customer)


@router.delete("/api/v1/customers/{id}", status_code=204, response_model=None)
def delete_customer(
    id: str,
    current_user: DispatcherUser,
    db: DbSession,
) -> None:
    """Soft-delete a customer."""
    customer = db.get(Customer, id)
    if not customer or customer.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer.deleted_at = datetime.now(timezone.utc)
    db.commit()
