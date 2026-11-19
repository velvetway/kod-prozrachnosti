#!/bin/bash
# Запуск прототипа на macOS двойным щелчком (или: ./start.command).
# 1) Docker (Docker Desktop или OrbStack): docker compose up — PostgreSQL + приложение.
# 2) Если Docker недоступен — Python: виртуальное окружение .venv, SQLite.
# Затем открывает http://localhost:8000 в браузере. Остановка — закрыть окно или Ctrl+C.

cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.orbstack/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
URL="http://localhost:8000"

wait_ready() {
  for _ in $(seq 1 90); do
    if curl -fsS "$URL/api/health" >/dev/null 2>&1; then
      echo "Готово: $URL  (вход: specialist / specialist или admin / admin)"
      open "$URL"
      return 0
    fi
    sleep 2
  done
  echo "Сервер не ответил за 3 минуты — смотрите сообщения выше."
  return 1
}

if command -v docker >/dev/null 2>&1; then
  if ! docker info >/dev/null 2>&1; then
    echo "Запускаю Docker…"
    open -a OrbStack 2>/dev/null || open -a Docker 2>/dev/null
    for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
  fi
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "Собираю и запускаю через Docker (первый раз — несколько минут)…"
  docker compose up --build -d || exit 1
  wait_ready
  echo "Журнал сервера (Ctrl+C — выйти из журнала; остановить: docker compose down):"
  docker compose logs -f app
else
  echo "Docker недоступен — запускаю через Python (SQLite)."
  PY=$(command -v python3.13 || command -v python3.12 || command -v python3)
  if [ -z "$PY" ]; then echo "Нужен Python 3.12+ или Docker."; read -r; exit 1; fi
  [ -d .venv ] || "$PY" -m venv .venv
  ./.venv/bin/pip install -q -r backend/requirements.txt || { echo "Не удалось установить зависимости."; read -r; exit 1; }
  if [ ! -f frontend/dist/index.html ]; then
    echo "Нет собранного интерфейса (frontend/dist): нужен Node.js — cd frontend && npm ci && npm run build"
    read -r; exit 1
  fi
  (sleep 3; wait_ready) &
  cd backend && exec ../.venv/bin/python -m uvicorn app.main:app --port 8000
fi
