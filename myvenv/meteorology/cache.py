from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict

_cache: Dict[str, Any] = {}
_cache_expiry: Dict[str, datetime] = {}


def simple_cache(expire_seconds: int = 300):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Проверяем есть ли валидный кэш
            if cache_key in _cache:
                if datetime.now() < _cache_expiry[cache_key]:
                    return _cache[cache_key]

            # Выполняем функцию и кэшируем результат
            result = await func(*args, **kwargs)
            _cache[cache_key] = result
            _cache_expiry[cache_key] = datetime.now() + timedelta(seconds=expire_seconds)

            return result

        return wrapper

    return decorator