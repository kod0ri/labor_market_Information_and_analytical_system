# Використовуємо офіційний легкий образ Python
FROM python:3.11-slim

# Встановлюємо системні залежності, необхідні для компіляції деяких Python-пакетів
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

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