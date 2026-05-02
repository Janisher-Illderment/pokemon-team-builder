## 1. Preparación del entorno

- [ ] 1.1 Añadir `fastapi`, `uvicorn[standard]`, `slowapi` a `pyproject.toml` como dependencias opcionales (`[project.optional-dependencies] web = [...]`)
- [ ] 1.2 Verificar que las dependencias se instalan correctamente con `pip install -e ".[web]"`

## 2. Capa API (FastAPI)

- [ ] 2.1 Crear `pokemon_team_builder/api/__init__.py` y `pokemon_team_builder/api/schemas.py` con los modelos Pydantic de request/response (`GenerateRequest`, `MemberOut`, `VariantOut`, `GenerateResponse`)
- [ ] 2.2 Crear `pokemon_team_builder/api/router.py` con `GET /health` y `POST /generate` (invoca `generate_team` + `to_pokepaste`)
- [ ] 2.3 Añadir validación de anchor contra el pool M-A en el endpoint (devuelve 422 si no está en el pool)
- [ ] 2.4 Configurar CORS middleware (`allow_origins=["*"]`) en la app principal
- [ ] 2.5 Crear punto de entrada `pokemon_team_builder/main.py` con `uvicorn.run` que lee `PORT` del entorno

## 3. Frontend estático

- [ ] 3.1 Crear `pokemon_team_builder/web/static/index.html` con estructura: header, formulario de búsqueda, área de resultados
- [ ] 3.2 Crear `pokemon_team_builder/web/static/app.js` con lógica Alpine.js: submit, loading state, render de tarjetas, copy to clipboard
- [ ] 3.3 Añadir estilos responsive (CSS inline o fichero separado) que funcionen en 375 px
- [ ] 3.4 Configurar FastAPI para servir `static/` con `StaticFiles` y ruta raíz `/` → `index.html`

## 4. Tests de la capa API

- [ ] 4.1 Crear `tests/test_api.py` con `TestClient` de FastAPI (sin llamadas reales a PokeAPI — usar fixtures)
- [ ] 4.2 Test `test_health_returns_200`
- [ ] 4.3 Test `test_generate_unknown_anchor_returns_422`
- [ ] 4.4 Test `test_generate_valid_anchor_returns_variants` (con pool fake de 6 Pokémon)

## 5. Docker y despliegue

- [ ] 5.1 Escribir `Dockerfile` (base `python:3.11-slim`, instala dependencias web, COPY package, CMD uvicorn)
- [ ] 5.2 Añadir `.dockerignore` (excluir `__pycache__`, `.git`, `tests/`, `openspec/`)
- [ ] 5.3 Verificar build local: `docker build -t poke-builder .` y `GET /health` pasa
- [ ] 5.4 Crear `railway.toml` con `[build] builder = "dockerfile"` y `[deploy] healthcheckPath = "/health"`
- [ ] 5.5 Deploy en Railway: conectar repo, activar auto-deploy desde `master`, verificar URL pública

## 6. CI

- [ ] 6.1 Añadir job `test-api` en `.github/workflows/ci.yml` que instala extras web y ejecuta `pytest tests/test_api.py`
