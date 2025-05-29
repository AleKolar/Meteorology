from sqlalchemy import Column, String, Float, Integer, DateTime, Index, ForeignKey
from sqlalchemy.orm import relationship, declared_attr
from sqlalchemy.dialects.postgresql import TSVECTOR
from myvenv.src.db.base import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), index=True)
    country = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    admin1 = Column(String(100), nullable=True)
    timezone = Column(String(50), default="UTC")

    # Добавляем TSVECTOR поле для полнотекстового поиска
    search_vector = Column(TSVECTOR)

    searches = relationship("SearchHistory", back_populates="location")

    @declared_attr
    def __table_args__(cls):
        return (
            # Обычный B-tree индекс
            Index('idx_location_name', 'name'),

            # GIN-индекс для поиска
            Index('idx_location_search_vector', 'search_vector', postgresql_using='gin'),

            # Дополнительный индекс для поиска по шаблону
            Index('idx_location_name_pattern', 'name',
                  postgresql_using='btree',
                  postgresql_ops={'name': 'varchar_pattern_ops'})
        )


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    location_id = Column(Integer, ForeignKey("locations.id"))
    city_name = Column(String(100))
    search_count = Column(Integer, default=1)
    last_searched = Column(DateTime)

    user = relationship("User", back_populates="search_history")
    location = relationship("Location", back_populates="searches")

    @declared_attr
    def __table_args__(cls):
        return (
            Index('idx_search_history_user', 'user_id'),
            Index('idx_search_history_location', 'location_id'),
            Index('idx_search_history_last_searched', 'last_searched'),
        )

