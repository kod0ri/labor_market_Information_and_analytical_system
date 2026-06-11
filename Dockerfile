# Використовуємо офіційний легкий образ Python
FROM python:3.11-slim

# Усі залежності (asyncpg, lxml, aiohttp) мають готові manylinux-wheels під cp311,
# тому компілятор не потрібен — образ менший і збірка швидша.

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо файл із залежностями
# (Переконайся, що в тебе є requirements.txt у корені)
COPY requirements.txt .

# Встановлюємо Python-залежності
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код проекту у контейнер
COPY . .

# Команда за замовчуванням для запуску твого пайплайну
CMD ["python", "run_pipeline.py"]