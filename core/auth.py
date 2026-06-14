import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from config.settings import settings

# Using standard Bearer Token scheme. Since login is dynamic, we point to login url
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

class UserSession(BaseModel):
    id: str
    username: str
    role: str

def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hashed bcrypt password."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a JWT token for user session payload."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserSession:
    """
    FastAPI dependency to extract and validate the JWT token.
    Raises 401 Unauthorized if the token is missing, invalid, or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    # Verify user session is active in Redis
    from core.redis import get_session
    session_data = await get_session(token)
    if session_data is None:
        raise credentials_exception
        
    username: str = session_data.get("username")
    role: str = session_data.get("role")
    user_id: str = session_data.get("id")
    
    if username is None or role is None or user_id is None:
        raise credentials_exception

    # Verify user exists in the database
    from database.sqlite_user_repo import user_repo
    user = user_repo.get_user(username)
    if user is None:
        raise credentials_exception

    return UserSession(
        id=user["id"],
        username=user["username"],
        role=user["role"]
    )

async def require_admin(current_user: UserSession = Depends(get_current_user)) -> UserSession:
    """
    FastAPI dependency that enforces the 'admin' role.
    Raises 403 Forbidden if the user is authenticated but not an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Special administration privileges required to perform this action"
        )
    return current_user
