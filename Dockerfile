FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY pokemon_team_builder/ ./pokemon_team_builder/

RUN pip install --no-cache-dir -e ".[web]"

ENV PORT=8000
EXPOSE 8000

CMD ["python", "-m", "pokemon_team_builder.main"]
