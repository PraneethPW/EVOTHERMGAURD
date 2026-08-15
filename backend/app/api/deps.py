from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.entities import User
from app.core.security import decode_token
bearer=HTTPBearer()
async def current_user(credentials:HTTPAuthorizationCredentials=Depends(bearer), db:AsyncSession=Depends(get_db)):
    try: user_id=decode_token(credentials.credentials)
    except Exception: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or expired token")
    user=await db.scalar(select(User).where(User.id==user_id))
    if not user: raise HTTPException(status_code=401,detail="User not found")
    return user
