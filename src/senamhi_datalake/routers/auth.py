"""/api/auth — Registration, login, profile."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..models.orm import User
from ..schemas.dto import LoginRequest, TokenOut, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    body: UserCreate, db: AsyncSession = Depends(get_session)
) -> UserOut:
    existing = (
        await db.execute(select(User).where(User.username == body.username))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="El usuario ya existe")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginRequest, db: AsyncSession = Depends(get_session)
) -> TokenOut:
    user = (
        await db.execute(select(User).where(User.username == body.username))
    ).scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token = create_access_token({"sub": user.username})
    return TokenOut(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(
    db: AsyncSession = Depends(get_session),
    current_user: str = Depends(get_current_user),
) -> UserOut:
    user = (
        await db.execute(
            select(User).where(User.username == current_user)
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return UserOut.model_validate(user)
