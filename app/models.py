from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base

video_genre_table = Table(
    "video_genre",
    Base.metadata,
    Column("video_id", ForeignKey("videos.id"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    videos = relationship("Video", back_populates="owner", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    liked_videos = relationship(
        "Video",
        secondary="video_likes",
        back_populates="liked_by",
    )
    subscriptions = relationship(
        "Subscription",
        foreign_keys="Subscription.subscriber_id",
        cascade="all, delete-orphan",
    )
    subscribers = relationship(
        "Subscription",
        foreign_keys="Subscription.channel_id",
        cascade="all, delete-orphan",
    )


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

    videos = relationship("Video", secondary=video_genre_table, back_populates="genres")


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    filename = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="videos")
    genres = relationship("Genre", secondary=video_genre_table, back_populates="videos")
    comments = relationship("Comment", back_populates="video", cascade="all, delete-orphan")
    liked_by = relationship(
        "User",
        secondary="video_likes",
        back_populates="liked_videos",
    )


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)

    author = relationship("User", back_populates="comments")
    video = relationship("Video", back_populates="comments")


class VideoLike(Base):
    __tablename__ = "video_likes"
    __table_args__ = (UniqueConstraint("user_id", "video_id", name="uq_video_like"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("subscriber_id", "channel_id", name="uq_subscription"),)

    id = Column(Integer, primary_key=True)
    subscriber_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    subscriber = relationship("User", foreign_keys=[subscriber_id], back_populates="subscriptions")
    channel = relationship("User", foreign_keys=[channel_id], back_populates="subscribers")
