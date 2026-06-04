from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Literal

from database.sqlite_user_repo import user_repo
from core.auth import (
    verify_password, 
    create_access_token, 
    get_current_user, 
    UserSession
)

router = APIRouter(prefix="/api/v1/auth", tags=["User Authentication"])

class RegisterSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=6, description="Minimum 6 characters password")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v.isalnum() and "_" not in v and "-" not in v:
            raise ValueError("Username must contain only alphanumeric characters, underscores, or hyphens.")
        return v.lower()

class LoginSchema(BaseModel):
    username: str
    password: str

class TokenSchema(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str

class UserProfileSchema(BaseModel):
    id: str
    username: str
    role: str

@router.post("/register", response_model=UserProfileSchema, status_code=status.HTTP_201_CREATED)
async def register(schema: RegisterSchema):
    """Register a new user account."""
    # Check if username exists
    existing = user_repo.get_user(schema.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken."
        )
    
    try:
        user = user_repo.create_user(
            username=schema.username,
            plain_password=schema.password,
            role="user"
        )
        return UserProfileSchema(
            id=user["id"],
            username=user["username"],
            role=user["role"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/login", response_model=TokenSchema)
async def login(schema: LoginSchema):
    """Authenticate credentials and generate a JWT access token."""
    username = schema.username.lower()
    user = user_repo.get_user(username)
    
    if not user or not verify_password(schema.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate token
    token_data = {
        "sub": user["username"],
        "role": user["role"],
        "user_id": user["id"]
    }
    access_token = create_access_token(data=token_data)
    
    return TokenSchema(
        access_token=access_token,
        token_type="bearer",
        role=user["role"],
        username=user["username"]
    )

@router.get("/me", response_model=UserProfileSchema)
async def get_my_profile(current_user: UserSession = Depends(get_current_user)):
    """Retrieve details of the currently authenticated user."""
    return UserProfileSchema(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role
    )
