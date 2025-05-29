from fastapi import APIRouter
from sqlalchemy import select, func

from myvenv.meteorology.models import Location, SearchHistory
from myvenv.meteorology.schemas import (
    WeatherResponse, SearchHistoryResponse, SearchHistoryItem,
)
from myvenv.src.db.database import database
from .repository import (
    fetch_weather_data,
    get_user_search_history,
    save_search_history_entry, GEOCODING_API_URL, logger, get_last_search_history
)

router = APIRouter(prefix="", tags=["weather"])

from fastapi import HTTPException, Depends
from typing import Optional, List
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"


@router.get("/weather/{city_name}", response_model=WeatherResponse)
async def get_weather(
        city_name: str,
        user_id: Optional[int] = None,
        db: AsyncSession = Depends(database.get_db)
) -> WeatherResponse:
    """
    Получение погоды по названию города (без SSL верификации)
    """
    if len(city_name) < 2:
        raise HTTPException(400, "Название города должно содержать минимум 2 символа")

    try:
        # Настройка HTTP-клиента без SSL верификации
        client_params = {
            "timeout": 30.0,
            "verify": False  # Отключаем проверку SSL
        }

        # Поиск города в базе или через API
        async with httpx.AsyncClient(**client_params) as client:
            # Сначала ищем в базе
            result = await db.execute(
                select(Location).where(Location.name.ilike(f"%{city_name}%")))
            location = result.scalars().first()

            if not location:
                # Запрос к API геокодинга
                geo_response = await client.get(
                    GEOCODING_API_URL,
                    params={"name": city_name, "count": 1, "language": "en"}
                )
                geo_response.raise_for_status()

                locations = geo_response.json().get("results", [])
                if not locations:
                    raise HTTPException(404, "Город не найден")

                # Сохраняем в базу
                loc_data = locations[0]
                location = Location(
                    name=loc_data.get("name"),
                    country=loc_data.get("country"),
                    latitude=loc_data.get("latitude"),
                    longitude=loc_data.get("longitude"),
                    admin1=loc_data.get("admin1", ""),
                    timezone=loc_data.get("timezone", "UTC")
                )
                db.add(location)
                await db.commit()
                await db.refresh(location)

            # 3. Запрос погоды
            weather_params = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": "temperature_2m,weather_code,precipitation,pressure_msl,wind_speed_10m,relative_humidity_2m",
                "hourly": "temperature_2m",
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": location.timezone,
                "forecast_days": 1
            }

            weather_response = await client.get(WEATHER_API_URL, params=weather_params)
            weather_response.raise_for_status()
            weather_data = weather_response.json()

        # 4. Формирование ответа
        current = weather_data.get("current", {})
        return WeatherResponse(
            city=location.name,
            country=location.country,
            temperature=current.get("temperature_2m"),
            weather_code=current.get("weather_code"),
            precipitation=current.get("precipitation", 0),
            pressure=current.get("pressure_msl"),
            windspeed=current.get("wind_speed_10m"),
            humidity=current.get("relative_humidity_2m"),
            hourly_temperatures=weather_data.get("hourly", {}).get("temperature_2m", [])[:24],
            max_temperature=weather_data.get("daily", {}).get("temperature_2m_max", [None])[0],
            min_temperature=weather_data.get("daily", {}).get("temperature_2m_min", [None])[0],
            last_updated=datetime.now()
        )

    except httpx.HTTPStatusError as e:
        logger.error(f"Ошибка API: {str(e)}")
        raise HTTPException(status_code=502, detail="Сервис погоды временно недоступен")
    except httpx.RequestError as e:
        logger.error(f"Ошибка соединения: {str(e)}")
        raise HTTPException(status_code=503, detail="Не удалось подключиться к сервису погоды")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")



@router.get("/current/{location_id}", response_model=WeatherResponse)
async def get_current_weather(
        location_id: int,
        user_id: Optional[int] = None,
        db: AsyncSession = Depends(database.get_db)
) -> WeatherResponse:
    """ Получение текущей погоды для указанного местоположения """
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(
            status_code=404,
            detail="Location not found"
        )

    # Сохраняем в историю, если указан user_id
    if user_id is not None:
        await save_search_history_entry(user_id, location_id, str(location.name), db)

    weather = await fetch_weather_data(location)
    if not weather:
        raise HTTPException(
            status_code=503,
            detail="Weather service unavailable"
        )
    return weather

@router.get("/history/last", response_model=SearchHistoryItem)
async def get_last_history_entry(
    user_id: int,
    db: AsyncSession = Depends(database.get_db)
):
    """Получение последней записи истории поиска"""
    last_entry = await get_last_search_history(user_id, db)
    if not last_entry:
        raise HTTPException(status_code=404, detail="No history found")
    return last_entry


@router.delete("/history/{record_id}", status_code=204)
async def delete_history_record(
        record_id: int,
        user_id: int,
        db: AsyncSession = Depends(database.get_db)
) -> None:
    """ Удаление записи из истории поиска """
    try:
        stmt = select(SearchHistory).where(
            SearchHistory.id == record_id,
            SearchHistory.user_id == user_id
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise HTTPException(
                status_code=404,
                detail="History record not found"
            )

        await db.delete(record)
        await db.commit()

        return None

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting history record: {str(e)}"
        )