import enum
from sqlalchemy import Integer, String, DateTime, ForeignKey, BigInteger, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime
from typing import List

from database.base import Base


class RoundStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Discord ID
    username: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    duration_minutes: Mapped[int] = mapped_column(Integer, default=5)
    round_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[RoundStatus] = mapped_column(Enum(RoundStatus), default=RoundStatus.IN_PROGRESS, nullable=False)

    meetings: Mapped[List["Meeting"]] = relationship("Meeting", back_populates="round", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Round(id={self.id}, #={self.round_number}, start={self.started_at})>"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id"), nullable=False)

    user_1_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_2_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    round: Mapped["Round"] = relationship("Round", back_populates="meetings")

    user_1: Mapped["User"] = relationship("User", foreign_keys=[user_1_id])
    user_2: Mapped["User"] = relationship("User", foreign_keys=[user_2_id])

    def __repr__(self):
        return f"<Meeting(round={self.round_id}, u1={self.user_1_id}, u2={self.user_2_id})>"
