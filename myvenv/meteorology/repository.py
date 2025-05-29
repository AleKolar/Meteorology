from datetime import datetime
from typing import List, Optional, Sequence
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from sqlalchemy.orm import selectinload

from myvenv.meteorology.models import Location, SearchHistory
from myvenv.meteorology.schemas import (
    WeatherResponse,
    SearchHistoryItem,
    SearchHistoryResponse
)

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

async def save_locations(db: AsyncSession, locations: list[dict]):
    for loc_data in locations:
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

# async def get_location_suggestions(query: str, db: AsyncSession) -> List[LocationSuggestion]:
#     """Поиск городов"""
#     try:
#         # Поиск в кэше (0Варианты написания)
#         stmt = select(Location).where(
#             func.lower(Location.name).ilike(f"%{query.lower()}%")
#         ).limit(10)
#
#         result = await db.execute(stmt)
#         cached = result.scalars().all()
#
#         if cached:
#             return [LocationSuggestion(
#                 id=loc.id,
#                 name=loc.name,
#                 country=loc.country,
#                 latitude=loc.latitude,
#                 longitude=loc.longitude
#             ) for loc in cached]
#
#         # Запрос к API
#         params = {
#             "name": query,
#             "count": 10,
#             "language": "ru",
#             "format": "json"
#         }
#
#         async with httpx.AsyncClient(timeout=5.0) as client:
#             response = await client.get(GEOCODING_API_URL, params=params)
#             response.raise_for_status()
#             api_data = response.json().get("results", [])
#
#         # Сохранение в БД
#         for loc in api_data:
#             stmt = insert(Location).values(
#                 id=loc["id"],
#                 name=loc["name"],
#                 country=loc["country"],
#                 latitude=loc["latitude"],
#                 longitude=loc["longitude"],
#                 admin1=loc.get("admin1"),
#                 timezone=loc.get("timezone", "UTC")
#             ).on_conflict_do_update(
#                 index_elements=['id'],
#                 set_={
#                     "name": loc["name"],
#                     "country": loc["country"],
#                     "latitude": loc["latitude"],
#                     "longitude": loc["longitude"]
#                 }
#             )
#             await db.execute(stmt)
#
#         await db.commit()
#         return [LocationSuggestion(**loc) for loc in api_data]
#
#     except Exception as e:
#         await db.rollback()
#         logger.error(f"Location search error: {str(e)}", exc_info=True)
#         return []

async def get_location_suggestions(db: AsyncSession, query: str, limit: int = 10) -> Sequence[Location]:
    # Сначала проверяем в базе
    stmt = select(Location).where(
        Location.name.ilike(f"%{query}%")
    ).limit(limit)
    result = await db.execute(stmt)
    locations = result.scalars().all()

    # Если в базе нет результатов, запрашиваем API
    if not locations:
        api_results = await fetch_locations_from_api(query, limit)
        if api_results:
            await save_locations(db, api_results)
            return await get_location_suggestions(db, query, limit)

    return locations

async def fetch_weather_data(location: Location) -> Optional[WeatherResponse]:
    """Получение данных о погоде"""
    try:
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": "temperature_2m,precipitation,pressure_msl,windspeed_10m",
            "timezone": location.timezone
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(WEATHER_API_URL, params=params)
            response.raise_for_status()
            data = response.json()["current"]

            return WeatherResponse(
                city=location.name,
                temperature=data["temperature_2m"],
                precipitation=data["precipitation"],
                pressure=data["pressure_msl"],
                windspeed=data["windspeed_10m"],
                last_updated=datetime.now()
            )
    except Exception as e:
        logger.error(f"Weather data error: {str(e)}")
        return None


async def get_search_history(user_id: int, db: AsyncSession) -> SearchHistoryResponse:
    """Исправленный запрос истории"""
    try:
        stmt = select(SearchHistory).options(
            selectinload(SearchHistory.location)
        ).filter(
            SearchHistory.user_id == user_id
        ).order_by(
            SearchHistory.last_searched.desc()
        )

        result = await db.execute(stmt)
        history = result.scalars().all()

        return SearchHistoryResponse(
            user_id=user_id,
            history=[
                SearchHistoryItem(
                    city_name=item.location.name if item.location else item.city_name,
                    last_searched=item.last_searched,
                    search_count=item.search_count
                ) for item in history
            ]
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
    """Сохранение истории поиска"""
    try:
        stmt = select(SearchHistory).filter(
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
        logger.error(f"Save history error: {str(e)}")
        raise