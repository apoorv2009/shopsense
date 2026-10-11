"""ASGI entrypoint: uvicorn order_platform.entrypoints.api:app"""

from order_platform.adapters.http.app import create_app
from order_platform.entrypoints.composition import build_engine, build_services
from order_platform.entrypoints.settings import Settings

app = create_app(build_services(build_engine(Settings())))
