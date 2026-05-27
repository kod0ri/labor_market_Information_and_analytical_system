import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.database import AsyncDatabasePool
from src.api.routes import analytics, health
from src.auth.router import router as auth_router
from src.admin.router import router as admin_router
from src.client.router import router as client_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await AsyncDatabasePool.initialize()
    yield
    await AsyncDatabasePool.close_all()


app = FastAPI(
    title="Labor Market Analytics API",
    description=(
        "REST API для інформаційно-аналітичної системи ринку праці України.\n\n"
        "Джерело даних: work.ua (вакансії та резюме IT-сектору).\n\n"
        "**Підсистеми:**\n"
        "- `/api/admin` — адміністративна підсистема (SOLID-принципи)\n"
        "- `/api/client` — клієнтська підсистема (GoF: Facade, Repository, Strategy, Factory)\n\n"
        "**Для React-розробника:** всі endpoint-и повертають JSON. "
        "Swagger UI доступний за адресою `/docs`."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["System"])
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
app.include_router(client_router, prefix="/api/client", tags=["Client"])
