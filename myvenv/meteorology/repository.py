from datetime import datetime
from typing import List, Optional, Sequence
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from fastapi import HTTPException

from sqlalchemy.orm import selectinload

from myvenv.meteorology.models import Location, SearchHistory
from myvenv.meteorology.schemas import (
    WeatherResponse,
    SearchHistoryItem,
    SearchHistoryResponse
)
from myvenv.src.db.models.models import User

logger = logging.getLogger("weather")

GEOCODING_API_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"


async def fetch_locations_from_api(name: str, count: int = 10) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            GEOCODING_API_URL,
            params={"name": name, "count": count, "language": "en", "format": "json"}
        )
        response.raise_for_status()
        return response.json().get("results", [])


async def save_location(db: AsyncSession, loc_data: dict) -> Location:
    """Сохраняет новое местоположение в базу"""
    location = Location(
        name=loc_data.get("name"),
        latitude=loc_data.get("latitude"),
        longitude=loc_data.get("longitude"),
        country=loc_data.get("country"),
        admin1=loc_data.get("admin1"),
        timezone=loc_data.get("timezone"),
    )
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return location


async def get_or_create_location(db: AsyncSession, query: str) -> Location:
    """Находит или создает местоположение"""
    # Сначала ищем в базе
    stmt = select(Location).where(Location.name.ilike(f"%{query}%"))
    result = await db.execute(stmt)
    location = result.scalars().first()

    # Если не нашли, запрашиваем API
    if not location:
        api_results = await fetch_locations_from_api(query, 1)
        if not api_results:
            raise HTTPException(404, "Location not found")
        location = await save_location(db, api_results[0])

    return location


async def fetch_weather_data(location: Location) -> WeatherResponse:
    """Получает данные о погоде для местоположения"""
    try:
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": "temperature_2m,weather_code,precipitation,pressure_msl,windspeed_10m,relative_humidity_2m",
            "hourly": "temperature_2m",
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": location.timezone
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(WEATHER_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

            current = data["current"]
            hourly = data["hourly"]
            daily = data["daily"]

            return WeatherResponse(
                city=location.name,
                country=location.country,
                temperature=current["temperature_2m"],
                weather_code=current["weather_code"],
                precipitation=current["precipitation"],
                pressure=current["pressure_msl"],
                windspeed=current["windspeed_10m"],
                humidity=current["relative_humidity_2m"],
                hourly_temperatures=hourly["temperature_2m"][:24],
                max_temperature=daily["temperature_2m_max"][0],  # Макс. сегодня
                min_temperature=daily["temperature_2m_min"][0],  # Мин. сегодня
                last_updated=datetime.now()
            )
    except httpx.HTTPError as e:
        logger.error(f"Weather API error: {str(e)}")
        raise HTTPException(503, "Weather service unavailable")
    except Exception as e:
        logger.error(f"Unexpected weather error: {str(e)}")
        raise HTTPException(500, "Internal server error")


async def get_weather_by_location_name(
        query: str,
        user_id: Optional[int] = None,
        db: AsyncSession = None
) -> WeatherResponse:
    """Основная функция для получения погоды по названию места"""
    if len(query) < 2:
        raise HTTPException(400, "Query too short")

    # Получаем или создаем местоположение
    location = await get_or_create_location(db, query)

    # Сохраняем в историю поиска, если указан user_id
    if user_id and db:
        await save_search_history(user_id, location.id, location.name, db)

    # Получаем данные о погоде
    return await fetch_weather_data(location)


async def get_search_history(user_id: int, db: AsyncSession) -> SearchHistoryResponse:
    """Получение истории поиска с данными о погоде"""
    try:
        stmt = select(SearchHistory).options(
            selectinload(SearchHistory.location)
        ).filter(
            SearchHistory.user_id == user_id
        ).order_by(
            SearchHistory.last_searched.desc()
        ).limit(10)  # Ограничиваем количество записей

        result = await db.execute(stmt)
        history = result.scalars().all()

        items = []
        for item in history:
            # Для каждой записи получаем текущую погоду
            weather = None
            if item.location:
                try:
                    weather = await fetch_weather_data(item.location)
                except Exception as e:
                    logger.error(f"Failed to get weather for history item: {str(e)}")

            items.append(SearchHistoryItem(
                city_name=item.location.name if item.location else item.city_name,
                last_searched=item.last_searched,
                search_count=item.search_count,
                current_weather=weather
            ))

        return SearchHistoryResponse(
            user_id=user_id,
            history=items
        )
    except Exception as e:
        logger.error(f"History error: {str(e)}", exc_info=True)
        return SearchHistoryResponse(user_id=user_id, history=[])


async def save_search_history(
        user_id: int,
        location_id: int,
        location_name: str,
        db: AsyncSession
) -> None:
    """Сохранение истории поиска с проверкой пользователя"""
    try:
        # Проверяем существование пользователя
        user_exists = await db.execute(
            select(User).where(User.id == user_id)
        )
        if not user_exists.scalar():
            logger.warning(f"Пользователь с ID {user_id} не существует")
            return

        # Проверяем существующую запись истории
        stmt = select(SearchHistory).where(
            SearchHistory.user_id == user_id,
            SearchHistory.location_id == location_id
        )
        result = await db.execute(stmt)
        existing = result.scalars().first()

        if existing:
            existing.search_count += 1
            existing.last_searched = datetime.now()
        else:
            db.add(SearchHistory(
                user_id=user_id,
                location_id=location_id,
                city_name=location_name,
                search_count=1,
                last_searched=datetime.now()
            ))

        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка сохранения истории: {str(e)}")
        raise