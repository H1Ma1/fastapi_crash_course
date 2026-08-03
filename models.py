from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    google_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)

    username: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)

    name: Mapped[str | None] = mapped_column(String, nullable=True)
    picture: Mapped[str | None] = mapped_column(String, nullable=True)

    items: Mapped[list["UserItem"]] = relationship(back_populates="user")


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    __table_args__ = (
        UniqueConstraint("title", "category", name="uq_catalog_title_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)

    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_approved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user_items: Mapped[list["UserItem"]] = relationship(back_populates="catalog_item")


class UserItem(Base):
    __tablename__ = "user_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    catalog_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_items.id"),
        nullable=True,
    )

    custom_title: Mapped[str | None] = mapped_column(String, nullable=True)

    category: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="planned", nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="items")
    catalog_item: Mapped["CatalogItem | None"] = relationship(back_populates="user_items")


class Friendship(Base):
    __tablename__ = "friendships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    requester: Mapped["User"] = relationship(
        "User",
        foreign_keys=[requester_id],
    )

    receiver: Mapped["User"] = relationship(
        "User",
        foreign_keys=[receiver_id],
    )