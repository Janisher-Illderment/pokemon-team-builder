## Why

La herramienta es actualmente una CLI Python que requiere instalación local. Exponerla como aplicación web elimina la barrera de instalación y permite que cualquier usuario (incluyendo el experto Champions que valida equipos) la use desde el navegador, sin depender del ejecutable portable.

## What Changes

- Añadir una capa de API REST (FastAPI) que envuelve los servicios existentes (`team_generator`, `replica_exporter`, `pokemon_lookup`)
- Añadir una interfaz web (HTML/CSS/JS o framework ligero) que consume la API
- El core Python existente no cambia — solo se expone a través de HTTP
- Añadir configuración de despliegue (Dockerfile + opción de hosting cloud)

## Capabilities

### New Capabilities

- `web-api`: Endpoints REST que reciben un nombre de Pokémon ancla y devuelven variantes de equipo en formato PokePaste + metadatos (score, roles, items)
- `web-ui`: Interfaz de usuario accesible desde el navegador — campo de búsqueda de Pokémon, visualización de equipos generados, botón de copia de PokePaste
- `deployment`: Configuración para levantar el servicio online (Dockerfile, variables de entorno, opción de Railway/Render/fly.io como hosting gratuito/barato)

### Modified Capabilities

<!-- ninguna — el core de generación no cambia de interfaz -->

## Impact

- `pokemon_team_builder/api/` (nuevo): router FastAPI con endpoints de generación
- `pokemon_team_builder/web/` o `static/` (nuevo): assets del frontend
- `pyproject.toml`: añadir `fastapi`, `uvicorn[standard]` como dependencias
- `Dockerfile` (nuevo): imagen de producción
- CI: añadir job de lint/test para la capa API
- No hay cambios en `team_generator.py`, `replica_exporter.py` ni modelos de dominio
