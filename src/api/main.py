"""
FastAPI-застосунок 503Work: точка збірки всіх підсистем API в один сервер.

Три групи роутів змонтовані під різними префіксами: публічна аналітика
й пошук (analytics/client) - без авторизації за задумом (дашборд відкритий),
адмінка (admin) - за JWT, tracking/health - службові. Життєвий цикл (lifespan)
гарантує, що пул БД, auth-схема і tracking-схема готові ДО прийому запитів,
і коректно закриваються при зупинці процесу.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.database import AsyncDatabasePool
from src.api.routes import analytics, health, tracking
from src.auth.bootstrap import init_auth
from src.auth.router import router as auth_router
from src.auth.security import get_secret_key
from src.admin.router import router as admin_router
from src.client.router import router as client_router
from src.tracking.bootstrap import ensure_tracking_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ініціалізація/очищення на весь час життя процесу uvicorn (ASGI lifespan).

    Порядок важливий: секрет перевіряється ДО з'єднання з БД (немає сенсу
    відкривати пул, якщо застосунок все одно впаде), а схеми auth/tracking
    готуються ДО yield, тобто до першого прийнятого HTTP-запиту.
    """
    # Fail fast: без валідного JWT_SECRET застосунок не повинен стартувати.
    get_secret_key()
    await AsyncDatabasePool.initialize()
    await init_auth()  # створює схему auth + засіває адміна з env
    await ensure_tracking_schema()  # таблиця analytics.visits
    yield
    await AsyncDatabasePool.close_all()


app = FastAPI(
    title="Labor Market Analytics API",
    description=(
        "REST API для інформаційно-аналітичної системи ринку праці України.\n\n"
        "Джерела даних: work.ua, robota.ua, dou.ua (вакансії та резюме).\n\n"
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
    "http://localhost:3000,http://localhost:5173",   # дефолт під локальну розробку (CRA-порт + Vite-порт)
).split(",")   # список дозволених origin-ів; у проді задається реальним доменом фронтенду через .env

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,       # явний allowlist, не "*", бо allow_credentials=True
    allow_credentials=True,            # потрібно для JWT-кукі/заголовків адмінки
    allow_methods=["GET", "POST", "PATCH"],  # рівно ті методи, що реально використовує API
    allow_headers=["*"],
)

# Кожен роутер монтується під власним префіксом - health без /api (для
# інфраструктурних liveness-перевірок за конвенцією), решта під /api/*.
app.include_router(health.router, tags=["System"])
app.include_router(tracking.router, prefix="/api", tags=["Tracking"])
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
app.include_router(client_router, prefix="/api/client", tags=["Client"])
