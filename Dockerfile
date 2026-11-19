# Сервер с уже собранным интерфейсом (frontend/dist лежит в репозитории).
# Интерфейс не собирается в образе: сборка React в Docker на arm64 падала из-за
# нативного парсера Rollup. Пересобрать интерфейс: cd frontend && npm ci && npm run build.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/app/data
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY data/reference data/reference
COPY demo demo
COPY frontend/dist frontend/dist
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
