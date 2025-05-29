from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from myvenv.meteorology.models import Location, SearchHistory
from myvenv.meteorology.schemas import (
    LocationSuggestion,
    WeatherResponse,
    SearchHistoryResponse
)
from myvenv.src.db.database import database
import httpx
from .repository import (
    fetch_weather_data,
    get_search_history,
    save_search_history, GEOCODING_API_URL, logger
)

router = APIRouter(prefix="", tags=["weather"])


@router.get("/weather/suggestions", response_model=List[LocationSuggestion])
async def get_suggestions(
        query: str,
        limit: int = 10,
        country: Optional[str] = None,
        db: AsyncSession = Depends(database.get_db)
) -> List[LocationSuggestion]:
    """
    Получение подсказок местоположений через Open-Meteo API
    """
    if len(query) < 2:
        raise HTTPException(400, "Query must be at least 2 characters")

    try:
        # Получаем данные из API
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                GEOCODING_API_URL,
                params={"name": query, "count": limit, "language": "en"}
            )
            response.raise_for_status()
            locations = response.json().get("results", [])

        return [
            LocationSuggestion(
                id=idx,
                name=loc.get("name"),
                country=loc.get("country"),
                admin1=loc.get("admin1"),
                latitude=loc.get("latitude"),
                longitude=loc.get("longitude"),
                timezone=loc.get("timezone")
            )
            for idx, loc in enumerate(locations, 1)
        ]

    except httpx.HTTPError as e:
        logger.error(f"API request failed: {e}")
        raise HTTPException(502, "Geocoding service unavailable")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(500, "Internal server error")


# @router.get("/suggestions", response_model=List[LocationSuggestion])
# async def get_suggestions(
#         query: str,
#         db: AsyncSession = Depends(database.get_db)
# ) -> List[LocationSuggestion]:
#     """
#     Получение подсказок местоположений по частичному названию.
#     """
#     if len(query) < 2:
#         raise HTTPException(
#             status_code=400,
#             detail="Query must be at least 2 characters long"
#         )
#
#     try:
#         stmt = select(Location).where(
#             func.lower(Location.name).ilike(f"%{query.lower()}%")
#         ).limit(10)
#
#         result = await db.execute(stmt)
#         locations = result.scalars().all()
#
#         return [
#             LocationSuggestion(
#                 id=loc.id,
#                 name=loc.name,
#                 country=loc.country,
#                 admin1=loc.admin1
#             )
#             for loc in locations
#         ]
#     except Exception as e:
#         logger.error(f"Location search error: {e}")
#         raise HTTPException(
#             status_code=500,
#             detail="Error searching locations"
#         )

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
        await save_search_history(user_id, location_id, str(location.name), db)

    weather = await fetch_weather_data(location)
    if not weather:
        raise HTTPException(
            status_code=503,
            detail="Weather service unavailable"
        )
    return weather

@router.get("/history", response_model=List[SearchHistoryResponse])
async def get_search_history(
        user_id: int,
        db: AsyncSession = Depends(database.get_db)
) -> List[SearchHistoryResponse]:
    """ Получение истории поиска погоды для пользователя """
    return await get_search_history(user_id, db)


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