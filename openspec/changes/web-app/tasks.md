## 1. Preparación del entorno

- [x] 1.1 Añadir `fastapi`, `uvicorn[standard]`, `slowapi` a `pyproject.toml` como dependencias opcionales (`[project.optional-dependencies] web = [...]`)
- [x] 1.2 Verificar que las dependencias se instalan correctamente con `pip install -e ".[web]"`

## 2. Capa API (FastAPI)

- [x] 2.1 Crear `pokemon_team_builder/api/__init__.py` y `pokemon_team_builder/api/schemas.py` con los modelos Pydantic de request/response (`GenerateRequest`, `MemberOut`, `VariantOut`, `GenerateResponse`)
- [x] 2.2 Crear `pokemon_team_builder/api/router.py` con `GET /health` y `POST /generate` (invoca `generate_team` + `to_pokepaste`)
- [x] 2.3 Añadir validación de anchor contra el pool M-A en el endpoint (devuelve 422 si no está en el pool)
- [x] 2.4 Configurar CORS middleware (`allow_origins=["*"]`) en la app principal
- [x] 2.5 Crear punto de entrada `pokemon_team_builder/main.py` con `uvicorn.run` que lee `PORT` del entorno

## 3. Frontend estático

- [x] 3.1 Crear `pokemon_team_builder/web/static/index.html` con estructura: header, formulario de búsqueda, área de resultados
- [x] 3.2 Crear `pokemon_team_builder/web/static/app.js` con lógica Alpine.js: submit, loading state, render de tarjetas, copy to clipboard
- [x] 3.3 Añadir estilos responsive (CSS inline o fichero separado) que funcionen en 375 px
- [x] 3.4 Configurar FastAPI para servir `static/` con `StaticFiles` y ruta raíz `/` → `index.html`

## 4. Tests de la capa API

- [x] 4.1 Crear `tests/test_api.py` con `TestClient` de FastAPI (sin llamadas reales a PokeAPI — usar fixtures)
- [x] 4.2 Test `test_health_returns_200`
- [x] 4.3 Test `test_generate_unknown_anchor_returns_422`
- [x] 4.4 Test `test_generate_valid_anchor_returns_variants` (con pool fake de 6 Pokémon)

## 5. Docker y despliegue

- [x] 5.1 Escribir `Dockerfile` (base `python:3.11-slim`, instala dependencias web, COPY package, CMD uvicorn)
- [x] 5.2 Añadir `.dockerignore` (excluir `__pycache__`, `.git`, `tests/`, `openspec/`)
- [ ] 5.3 Verificar build local: `docker build -t poke-builder .` y `GET /health` pasa  ← requiere Docker Desktop
- [x] 5.4 Crear `railway.toml` con `[build] builder = "dockerfile"` y `[deploy] healthcheckPath = "/health"`
- [ ] 5.5 Deploy en Railway: conectar repo, activar auto-deploy desde `master`, verificar URL pública  ← requiere push + cuenta Railway

## 6. CI

- [x] 6.1 Añadir job `test-api` en `.github/workflows/ci.yml` que instala extras web y ejecuta `pytest tests/test_api.py`
