from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship

from myvenv.src.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    hashed_password = Column(String, nullable=False)
    search_history = relationship("SearchHistory", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"