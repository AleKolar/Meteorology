import logging
from datetime import datetime
from typing import Optional, List
import httpx
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from myvenv.src.db.models.models import User
from myvenv.meteorology.models import Location, SearchHistory
from myvenv.meteorology.schemas import WeatherResponse, SearchHistoryResponse, SearchHistoryItem

logger = logging.getLogger("weather")

GEOCODING_API_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"


async def fetch_locations_from_api(name: str, count: int = 10) -> List[dict]:
    """Получение местоположений через API"""
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            GEOCODING_API_URL,
            params={"name": name, "count": count, "language": "en", "format": "json"}
        )
        response.raise_for_status()
        return response.json().get("results", [])


async def save_location(db: AsyncSession, loc_data: dict) -> Location:
    """Сохранение местоположения в базу данных"""
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
    """Поиск или создание местоположения"""
    # Поиск в базе данных
    stmt = select(Location).where(Location.name.ilike(f"%{query}%"))
    result = await db.execute(stmt)
    location = result.scalars().first()

    # Если не найдено, запрашиваем API
    if not location:
        api_results = await fetch_locations_from_api(query, 1)
        if not api_results:
            raise HTTPException(status_code=404, detail="Location not found")
        location = await save_location(db, api_results[0])

    return location


async def fetch_weather_data(location: Location) -> Optional[WeatherResponse]:
    """Получение данных о погоде"""
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            params = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": "temperature_2m,weather_code,precipitation,pressure_msl,wind_speed_10m,relative_humidity_2m",
                "hourly": "temperature_2m",
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": location.timezone or "auto",
                "forecast_days": 1
            }

            response = await client.get(WEATHER_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

            current = data.get("current", {})
            return WeatherResponse(
                city=location.name,
                country=location.country,
                temperature=current.get("temperature_2m"),
                weather_code=current.get("weather_code"),
                precipitation=current.get("precipitation", 0),
                pressure=current.get("pressure_msl"),
                windspeed=current.get("wind_speed_10m"),
                humidity=current.get("relative_humidity_2m"),
                hourly_temperatures=data.get("hourly", {}).get("temperature_2m", [])[:24],
                max_temperature=data.get("daily", {}).get("temperature_2m_max", [None])[0],
                min_temperature=data.get("daily", {}).get("temperature_2m_min", [None])[0],
                last_updated=datetime.now()
            )
    except Exception as e:
        logger.error(f"Failed to fetch weather: {str(e)}", exc_info=True)
        return None


async def get_weather_by_location_name(
    query: str,
    user_id: Optional[int] = None,
    db: Optional[AsyncSession] = None
) -> WeatherResponse:
    """Получение погоды по названию места"""
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Query too short")

    if not db:
        raise HTTPException(status_code=500, detail="Database session not provided")

    location = await get_or_create_location(db, query)

    if user_id:
        await save_search_history_entry(user_id, location.id, location.name, db)

    weather = await fetch_weather_data(location)
    if not weather:
        raise HTTPException(status_code=503, detail="Weather service unavailable")

    return weather


async def get_user_search_history(user_id: int, db: AsyncSession) -> SearchHistoryResponse:
    """Получение истории поиска пользователя"""
    try:
        user = await db.get(User, user_id)
        if not user:
            logger.warning(f"User {user_id} not found")
            return SearchHistoryResponse(user_id=user_id, history=[])

        stmt = (select(SearchHistory)
               .options(selectinload(SearchHistory.location))
               .filter(SearchHistory.user_id == user_id)
               .order_by(desc(SearchHistory.last_searched))
               .limit(10))

        result = await db.execute(stmt)
        history_items = result.scalars().all()

        items = []
        for item in history_items:
            weather = None
            if item.location:
                try:
                    weather = await fetch_weather_data(item.location)
                except Exception as e:
                    logger.error(f"Failed to fetch weather: {str(e)}")

            items.append(SearchHistoryItem(
                user_id=user_id,  # Добавлено обязательное поле
                city_name=item.location.name if item.location else item.city_name,
                search_count=item.search_count,
                last_searched=item.last_searched,
                current_weather=weather
            ))

        return SearchHistoryResponse(user_id=user_id, history=items)

    except Exception as e:
        logger.error(f"History error: {str(e)}", exc_info=True)
        return SearchHistoryResponse(user_id=user_id, history=[])

async def get_last_search_history(user_id: int, db: AsyncSession) -> Optional[SearchHistoryItem]:
    """Получение последней записи истории поиска"""
    try:
        stmt = (select(SearchHistory)
               .options(selectinload(SearchHistory.location))
               .filter(SearchHistory.user_id == user_id)
               .order_by(desc(SearchHistory.last_searched))
               .limit(1))

        result = await db.execute(stmt)
        last_entry = result.scalar_one_or_none()

        if not last_entry:
            return None

        weather = None
        if last_entry.location:
            try:
                weather = await fetch_weather_data(last_entry.location)
            except Exception as e:
                logger.error(f"Failed to fetch weather: {str(e)}")

        return SearchHistoryItem(
            user_id=user_id,
            city_name=last_entry.location.name if last_entry.location else last_entry.city_name,
            search_count=last_entry.search_count,
            last_searched=last_entry.last_searched,
            current_weather=weather
        )

    except Exception as e:
        logger.error(f"Error getting last history: {str(e)}", exc_info=True)
        return None


async def save_search_history_entry(
    user_id: int,
    location_id: int,
    location_name: str,
    db: AsyncSession
) -> bool:
    """Сохранение записи в историю поиска"""
    try:
        user = await db.get(User, user_id)
        if not user:
            logger.warning(f"User {user_id} not found")
            return False

        location = await db.get(Location, location_id)
        if not location:
            logger.warning(f"Location {location_id} not found")
            return False

        result = await db.execute(
            select(SearchHistory)
            .where(
                SearchHistory.user_id == user_id,
                SearchHistory.location_id == location_id
            )
        )
        existing = result.scalar_one_or_none()

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
        return True

    except Exception as e:
        await db.rollback()
        logger.error(f"Save history error: {str(e)}", exc_info=True)
        return False