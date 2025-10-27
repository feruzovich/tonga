from __future__ import annotations

import os
import shutil
import uuid
from typing import List

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, schemas
from .database import SessionLocal, init_db
from .security import create_access_token, decode_token, get_password_hash, verify_password

app = FastAPI(title="ClipStream")


@app.on_event("startup")
def on_startup() -> None:
    os.makedirs("uploads", exist_ok=True)
    init_db()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    payload = decode_token(token)
    username: str | None = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@app.post("/auth/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")
    user = models.User(
        username=user_in.username,
        password_hash=get_password_hash(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token = create_access_token({"sub": user.username})
    return schemas.Token(access_token=access_token)


@app.get("/users/me", response_model=schemas.UserOut)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.post("/videos", response_model=schemas.VideoOut, status_code=status.HTTP_201_CREATED)
async def upload_video(
    title: str = Form(...),
    description: str | None = Form(None),
    genres: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join("uploads", filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    video = models.Video(title=title, description=description, filename=filename, owner=current_user)

    genre_names = [g.strip() for g in genres.split(",") if g.strip()]
    for name in genre_names:
        genre = db.query(models.Genre).filter(func.lower(models.Genre.name) == name.lower()).first()
        if not genre:
            genre = models.Genre(name=name)
            db.add(genre)
            db.flush()
        video.genres.append(genre)

    db.add(video)
    db.commit()
    db.refresh(video)
    return serialize_video(video, db)


@app.get("/videos", response_model=List[schemas.VideoOut])
def list_videos(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    videos = db.query(models.Video).order_by(models.Video.created_at.desc()).offset(skip).limit(limit).all()
    return [serialize_video(video, db) for video in videos]


@app.get("/videos/{video_id}", response_model=schemas.VideoOut)
def get_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return serialize_video(video, db)


@app.post("/videos/{video_id}/comments", response_model=schemas.CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    video_id: int,
    comment_in: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    comment = models.Comment(content=comment_in.content, author=current_user, video=video)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@app.post("/videos/{video_id}/like", status_code=status.HTTP_200_OK)
def like_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    existing_like = (
        db.query(models.VideoLike)
        .filter(models.VideoLike.user_id == current_user.id, models.VideoLike.video_id == video.id)
        .first()
    )
    if existing_like:
        db.delete(existing_like)
        message = "Like removed"
    else:
        like = models.VideoLike(user_id=current_user.id, video_id=video.id)
        db.add(like)
        message = "Video liked"
    db.commit()
    return {"detail": message}


@app.post("/users/{user_id}/subscribe", status_code=status.HTTP_200_OK)
def subscribe_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot subscribe to yourself")
    channel = db.query(models.User).filter(models.User.id == user_id).first()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    existing = (
        db.query(models.Subscription)
        .filter(
            models.Subscription.subscriber_id == current_user.id,
            models.Subscription.channel_id == channel.id,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        message = "Unsubscribed"
    else:
        subscription = models.Subscription(subscriber_id=current_user.id, channel_id=channel.id)
        db.add(subscription)
        message = "Subscribed"
    db.commit()
    return {"detail": message}


@app.get("/users/me/recommendations", response_model=List[schemas.RecommendationOut])
def get_recommendations(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    liked_genre_ids = [
        genre_id
        for (genre_id,) in (
            db.query(models.Genre.id)
            .join(models.video_genre_table, models.Genre.id == models.video_genre_table.c.genre_id)
            .join(models.Video, models.Video.id == models.video_genre_table.c.video_id)
            .join(models.VideoLike, models.VideoLike.video_id == models.Video.id)
            .filter(models.VideoLike.user_id == current_user.id)
            .distinct()
            .all()
        )
    ]
    if not liked_genre_ids:
        return []

    recommendations = (
        db.query(models.Video, func.count(models.Genre.id).label("score"))
        .join(models.video_genre_table, models.Video.id == models.video_genre_table.c.video_id)
        .join(models.Genre, models.Genre.id == models.video_genre_table.c.genre_id)
        .filter(models.Genre.id.in_(liked_genre_ids))
        .filter(models.Video.owner_id != current_user.id)
        .group_by(models.Video.id)
        .order_by(func.count(models.Genre.id).desc(), models.Video.created_at.desc())
        .limit(20)
        .all()
    )

    return [
        schemas.RecommendationOut(video=serialize_video(video, db), score=score)
        for video, score in recommendations
    ]


def serialize_video(video: models.Video, db: Session) -> schemas.VideoOut:
    likes = db.query(func.count(models.VideoLike.id)).filter(models.VideoLike.video_id == video.id).scalar() or 0
    db.refresh(video)
    return schemas.VideoOut(
        id=video.id,
        title=video.title,
        description=video.description,
        filename=video.filename,
        created_at=video.created_at,
        owner=video.owner,
        genres=list(video.genres),
        likes=likes,
    )


app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
