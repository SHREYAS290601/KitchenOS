from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import Settings
from backend.app.db import make_engine, make_session_factory
from backend.app.routes import assist, consent, consumption, health, images, pantry, shopping
from backend.app.storage import make_object_store


def create_app() -> FastAPI:
    settings = Settings()
    engine = make_engine(settings.database_url)

    app = FastAPI(title="PantryOps Edge", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8081", "http://127.0.0.1:8081"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.object_store = make_object_store(settings)

    app.include_router(health.router)
    app.include_router(pantry.router)
    app.include_router(shopping.router)
    app.include_router(consent.router)
    app.include_router(images.router)
    app.include_router(assist.router)
    app.include_router(consumption.router)

    return app
