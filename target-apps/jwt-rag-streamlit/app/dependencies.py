from typing import Annotated
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.collection import Collection, CollectionMembership
from app.models.pg_types import UserRole, CollectionMemberRole
from app.services.auth import decode_access_token

# Type aliases for dependency injection
DbSession = Annotated[Session, Depends(get_db)]


# def _user_role(user: User) -> UserRole:
#     role = user.role
#     return role if isinstance(role, UserRole) else UserRole(role)


def get_current_user(db: DbSession, authorization: str | None = Header(default=None)) -> User:
    """Get current user from JWT token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    
    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


# Type alias for authenticated user
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(current_user: CurrentUser) -> User:
    """Require admin role"""
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


def require_contributor(current_user: CurrentUser) -> User:
    """Require contributor or admin role"""
    if current_user.role not in (UserRole.contributor, UserRole.admin):
        raise HTTPException(status_code=403, detail="Contributor privileges required")
    return current_user


def get_user_collection_access(db: DbSession, user: User, collection_id: int) -> CollectionMemberRole:
    """Get user's access level to a collection"""
    # Collection owners have admin access
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    if collection.owner_id == user.id:
        return CollectionMemberRole.contributor  # Owner has full access
    
    # Check membership
    membership = db.query(CollectionMembership).filter(
        CollectionMembership.collection_id == collection_id,
        CollectionMembership.user_id == user.id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Access denied to this collection")
    
    return CollectionMemberRole(membership.role)


def require_collection_access(collection_id: int, min_role: CollectionMemberRole = CollectionMemberRole.viewer):
    """Dependency factory for collection access control"""
    def _check_access(db: DbSession, current_user: CurrentUser) -> CollectionMemberRole:
        user_role = get_user_collection_access(db, current_user, collection_id)
        
        # Check if user has sufficient privileges
        role_hierarchy = {CollectionMemberRole.viewer: 0, CollectionMemberRole.contributor: 1}
        
        if role_hierarchy.get(user_role, 0) < role_hierarchy.get(min_role, 0):
            raise HTTPException(status_code=403, detail="Insufficient privileges for this collection")
        
        return user_role
    
    return _check_access
