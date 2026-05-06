FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir ".[web]"

ENV PORT=8000
EXPOSE 8000

CMD uvicorn pokemon_team_builder.main:app --host 0.0.0.0 --port ${PORT:-8000}
