from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token,
    decode_token, get_current_user
)
from app.models.user import User
from app.schemas.schemas import (
    UserRegister, UserLogin, TokenResponse,
    RefreshTokenRequest, UserBase, UserUpdate, MessageResponse
)
import random

router = APIRouter(prefix="/auth", tags=["Authentication"])

AVATAR_COLORS = ["#6366f1", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#ef4444", "#14b8a6"]

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        avatar_color=random.choice(AVATAR_COLORS)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)

@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    token_data = decode_token(payload.refresh_token)
    if not token_data or token_data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.query(User).filter(User.id == int(token_data["sub"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    access_token = create_access_token({"sub": str(user.id)})
    new_refresh = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(access_token=access_token, refresh_token=new_refresh)

@router.get("/me", response_model=UserBase)
def get_me(current_user=Depends(get_current_user)):
    return current_user

@router.patch("/me", response_model=UserBase)
def update_me(payload: UserUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if payload.name:
        current_user.name = payload.name
    if payload.avatar_color:
        current_user.avatar_color = payload.avatar_color
    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/users", response_model=list[UserBase])
def list_users(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Admin sees all users. Members see only colleagues in shared teams."""
    if current_user.role == "admin":
        return db.query(User).filter(User.is_active == True).all()
    
    # Find team IDs the current user belongs to
    from app.models.user import TeamMember
    my_team_ids = [tm.team_id for tm in db.query(TeamMember).filter(TeamMember.user_id == current_user.id).all()]
    
    if not my_team_ids:
        # Not in any team — can only see themselves
        return [current_user]
    
    # Get all user IDs who share a team with this user
    colleague_ids = db.query(TeamMember.user_id).filter(
        TeamMember.team_id.in_(my_team_ids)
    ).distinct().all()
    colleague_ids = [r[0] for r in colleague_ids]
    
    return db.query(User).filter(User.id.in_(colleague_ids), User.is_active == True).all()
