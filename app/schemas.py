from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: str | None = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        orm_mode = True


class GenreOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class CommentOut(BaseModel):
    id: int
    content: str
    created_at: datetime
    author: UserOut

    class Config:
        orm_mode = True


class VideoBase(BaseModel):
    title: str
    description: Optional[str]
    genres: List[str] = []


class VideoCreate(VideoBase):
    pass


class VideoOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    filename: str
    created_at: datetime
    owner: UserOut
    genres: List[GenreOut]
    likes: int

    class Config:
        orm_mode = True


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


class SubscriptionOut(BaseModel):
    channel: UserOut
    created_at: datetime

    class Config:
        orm_mode = True


class RecommendationOut(BaseModel):
    video: VideoOut
    score: int
