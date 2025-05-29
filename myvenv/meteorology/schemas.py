from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

class CitySuggestion(BaseModel):
    name: str
    country: str
    latitude: float
    longitude: float

class LocationSuggestion(BaseModel):
    id: int
    name: str
    country: str
    admin1: Optional[str]
    latitude: float
    longitude: float
    timezone: Optional[str]

class WeatherResponse(BaseModel):
    city: str
    country: str
    temperature: float
    weather_code: int
    precipitation: float
    pressure: float
    windspeed: float
    humidity: float
    hourly_temperatures: List[float]
    max_temperature: float
    min_temperature: float
    last_updated: datetime

class SearchHistoryItem(BaseModel):
    user_id: int
    city_name: str
    search_count: int
    last_searched: datetime

class SearchHistoryResponse(BaseModel):
    user_id: int
    history: List[SearchHistoryItem]

class LocationQuery(BaseModel):
    query: str

class WeatherRequest(BaseModel):
    user_id: int
    location_id: int