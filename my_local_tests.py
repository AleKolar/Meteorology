# import jwt
#
# payload = {"user_id": 123}
# secret = "your_secret"
# token = jwt.encode(payload, secret, algorithm='HS256')
#
# print("TOKEN:", token)

# import jwt
#
# payload = {"user_id": 123}
# secret = "your_secret"
#
# token = jwt.encode(payload, secret, algorithm='HS256')
# print(token)

# import asyncio
#
# from myvenv.src.core.security import send_verification_email
#
#
# async def test_email():
#     result = await send_verification_email("gefest-173@rambler.ru", "mn14071979")
#     print("Result:", result)
#
# asyncio.run(test_email())

# import certifi
# print(certifi.where())
# import os
# print(os.getenv('SSL_CERT_FILE'))
# import os
# cert_path = r'C:\Users\User\pythonProject\Deduplicator_python_fastapi\Meteorology\Lib\site-packages\certifi\cacert.pem'
# print(os.path.exists(cert_path))

# import requests
#
# url = "https://geocoding-api.open-meteo.com/v1/search"
# params = {
#     "name": "Moscow",
#     "count": 10,
#     "language": "en",
#     "format": "json",
# }
#
# response = requests.get(url, params=params)
# print(response.json())

from sqlalchemy import inspect, engine

inspector = inspect(engine)
print(inspector.get_columns('search_history'))
