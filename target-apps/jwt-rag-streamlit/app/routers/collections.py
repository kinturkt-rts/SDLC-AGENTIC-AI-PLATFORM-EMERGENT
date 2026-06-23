from typing import List
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.dependencies import DbSession, CurrentUser, require_admin
from app.models.collection import Collection, CollectionMembership
from app.models.document import Document
from app.models.user import User
from app.models.pg_types import CollectionMemberRole, UserRole
from app.services.audit import log_audit_event
from schemas.collection import CreateCollection, CollectionSummary, Collection as CollectionSchema, AddMember, Membership

router = APIRouter()


@router.get("/", response_model=List[CollectionSummary])
def list_collections(current_user: CurrentUser, db: DbSession):
    """List collections accessible to current user"""
    # Get collections where user is owner or member
    query = db.query(
        Collection,
        func.coalesce(func.count(Document.id), 0).label('document_count'),
        CollectionMembership.role.label('user_role')
    ).outerjoin(Document, Collection.id == Document.collection_id)
    
    # Join memberships for non-owners
    query = query.outerjoin(
        CollectionMembership,
        (Collection.id == CollectionMembership.collection_id) & 
        (CollectionMembership.user_id == current_user.id)
    )
    
    # Filter for accessible collections
    query = query.filter(
        (Collection.owner_id == current_user.id) | 
        (CollectionMembership.user_id == current_user.id)
    ).group_by(Collection.id, CollectionMembership.role)
    
    results = []
    for collection, doc_count, member_role in query.all():
        # Determine user role (owner gets contributor role)
        if collection.owner_id == current_user.id:
            user_role = CollectionMemberRole.contributor
        else:
            user_role = CollectionMemberRole(member_role)
        
        results.append(CollectionSummary(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            archived=collection.archived,
            document_count=doc_count or 0,
            user_role=user_role,
            created_at=collection.created_at
        ))
    
    return results


@router.post("/", response_model=CollectionSchema, status_code=201)
def create_collection(
    request: Request,
    body: CreateCollection,
    current_user: CurrentUser,
    db: DbSession
):
    """Create a new collection (admin/contributor only)"""
    # Check if user can create collections
    if current_user.role not in (UserRole.contributor, UserRole.admin):
        raise HTTPException(status_code=403, detail="Insufficient privileges to create collections")
    
    # Check if collection name already exists
    existing = db.query(Collection).filter(Collection.name == body.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Collection name already exists")
    
    # Create collection
    collection = Collection(
        name=body.name,
        description=body.description,
        owner_id=current_user.id
    )
    
    db.add(collection)
    db.commit()
    db.refresh(collection)
    
    # Log creation
    log_audit_event(
        db=db,
        user_id=current_user.id,
        action="collection_created",
        resource_type="collection",
        resource_id=collection.id,
        details={"name": collection.name},
        ip_address=request.client.host if request.client else None
    )
    
    return collection


@router.post("/{collection_id}/members", response_model=Membership, status_code=201)
def add_member(
    collection_id: int,
    body: AddMember,
    request: Request,
    current_user: CurrentUser,
    db: DbSession
):
    """Add member to collection (admin only)"""
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    # Check if collection exists
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    # Check if user exists
    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if membership already exists
    existing = db.query(CollectionMembership).filter(
        CollectionMembership.collection_id == collection_id,
        CollectionMembership.user_id == body.user_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member of this collection")
    
    # Create membership
    membership = CollectionMembership(
        collection_id=collection_id,
        user_id=body.user_id,
        role=body.role.value
    )
    
    db.add(membership)
    db.commit()
    db.refresh(membership)
    
    # Log membership addition
    log_audit_event(
        db=db,
        user_id=current_user.id,
        action="member_added",
        resource_type="collection",
        resource_id=collection_id,
        details={"added_user_id": body.user_id, "role": body.role.value},
        ip_address=request.client.host if request.client else None
    )
    
    return membership
