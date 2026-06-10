"""
Auth routes — self-registration (client role) + login + current user.
Admins are seeded server-side (see db._seed_users); registration can never
create an admin.
"""
import re

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core.auth import (
    hash_password, verify_password, create_access_token, get_current_user,
)
from db.postgres import create_user, get_user_by_username

router = APIRouter()


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=4, max_length=128)


def _token_response(user: dict) -> dict:
    dept = user.get("department")
    token = create_access_token(user["id"], user["username"], user["role"], dept)
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": user["id"], "username": user["username"],
                     "role": user["role"], "department": dept}}


@router.post("/register")
async def register(body: Credentials):
    username = body.username.strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]+", username):
        raise HTTPException(status_code=400,
                            detail="Username may only contain letters, numbers, . _ -")
    # Self-registration always creates a CLIENT — never an admin.
    created = await create_user(username, hash_password(body.password), role="client")
    if created is None:
        raise HTTPException(status_code=409, detail="That username is already taken")
    return _token_response(created)


@router.post("/login")
async def login(body: Credentials):
    username = body.username.strip().lower()
    user = await get_user_by_username(username)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return _token_response(user)


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user
