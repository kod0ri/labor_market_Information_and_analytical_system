import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.database import AsyncDatabasePool
from src.api.routes import analytics, vacancies, health


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
        "**Для React-розробника:** всі endpoint-и повертають JSON. "
        "Swagger UI доступний за адресою `/docs`."
    ),
    version="1.0.0",
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
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["System"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(vacancies.router, prefix="/api/vacancies", tags=["Vacancies"])
