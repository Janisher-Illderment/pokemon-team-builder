FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir ".[web]"

ENV PORT=8000
EXPOSE 8000

CMD ["python", "-m", "pokemon_team_builder.main"]
