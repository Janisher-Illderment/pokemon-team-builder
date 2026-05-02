## Context

El proyecto es una CLI Python con arquitectura limpia en capas: `domain/` (modelos), `services/` (lógica pura), y `cli.py` (punto de entrada). Los servicios no tienen estado y son fácilmente invocables desde una capa HTTP. La generación de un equipo completo implica llamadas a PokeAPI (latencia ~1-3 s en cold call, cacheadas con hishel), por lo que la API debe ser async y comunicar progreso al cliente.

## Goals / Non-Goals

**Goals:**
- Exponer `generate_team` y `to_pokepaste` como endpoints HTTP sin modificar la lógica existente
- UI mínima pero funcional: buscar Pokémon ancla → ver 3 variantes → copiar PokePaste
- Despliegue reproducible con Docker
- Coste de hosting ≤ €0–5/mes (tier gratuito de Railway/Render/fly.io es suficiente para tráfico bajo)

**Non-Goals:**
- Autenticación / cuentas de usuario — la herramienta es anónima por diseño
- Base de datos persistente — sin historial de equipos por usuario
- UI avanzada (comparador de equipos, editor de moveset, etc.) — eso es v2
- Rate limiting robusto para tráfico alto — mínimo básico es suficiente para uso personal/comunidad pequeña

## Decisions

**Decisión 1: FastAPI como framework API**
- FastAPI permite definir endpoints async con validación Pydantic (ya usamos Pydantic en domain/models)
- Alternativa descartada: Flask (síncrono, más friction para async); Django (overkill)
- Integración natural: los modelos de dominio ya son Pydantic, se pueden serializar directamente

**Decisión 2: Server-Sent Events (SSE) para progreso de generación**
- La generación tarda 2-5 s; el cliente necesita feedback antes de recibir el resultado
- SSE es más simple que WebSockets para streaming unidireccional server→client
- Alternativa descartada: polling del cliente (más complejo, más requests); WebSockets (overhead innecesario)

**Decisión 3: Frontend sin framework pesado (HTML + Alpine.js o vanilla JS)**
- El UI es simple: un formulario + lista de resultados. No justifica React/Vue.
- Alpine.js (~15 KB) da reactividad mínima sin build step
- Alternativa descartada: React (build step, node_modules, overkill); Jinja2 SSR (no da UX reactiva)

**Decisión 4: Hosting con Railway (free tier)**
- Railway detecta Dockerfile automáticamente, da dominio público gratis, soporta environment variables
- Alternativa: Render (también gratuito, cold starts más lentos); fly.io (más config manual)
- Alternativa descartada: Vercel/Netlify (serverless, no adecuado para procesos Python de larga duración)

**Decisión 5: Estructura de directorios**
```
pokemon_team_builder/
  api/
    __init__.py
    router.py        # FastAPI router con endpoints /generate, /health
    schemas.py       # Request/Response Pydantic models (separados del domain)
  web/
    static/
      index.html
      app.js
```
- Alternativa descartada: carpeta `web/` en raíz del proyecto — mejor mantener todo bajo el package

## Risks / Trade-offs

- [Riesgo] PokeAPI rate limit bajo carga concurrente → Mitigación: hishel ya cachea respuestas; añadir límite de 2 requests simultáneos por IP con slowapi
- [Riesgo] Cold start en Railway free tier (hasta 30 s tras inactividad) → Mitigación: documentar en UI con mensaje de "iniciando..." via SSE
- [Trade-off] Sin persistencia = sin historial → Aceptable para v1; el usuario copia el PokePaste manualmente

## Migration Plan

1. Instalar `fastapi`, `uvicorn[standard]` (ya en pyproject.toml extras o dependencia directa)
2. Implementar `api/router.py` y `api/schemas.py`
3. Añadir punto de entrada `main.py` o `__main__.py` con `uvicorn.run`
4. Construir frontend estático en `web/static/`
5. Escribir `Dockerfile` (imagen slim, COPY del package, CMD uvicorn)
6. Deploy en Railway: conectar repo GitHub, configurar variable `PORT`
7. Rollback: el CLI existente no se toca; revertir solo el directorio `api/`

## Open Questions

- ¿El endpoint `/generate` debe devolver las 3 variantes de golpe (una sola response JSON) o via SSE variante a variante? → Recomendación: SSE variante a variante da mejor UX
- ¿Incluir el PokePaste directamente en la response JSON o como endpoint separado `/export/{variant_id}`? → Respuesta en response directa es más simple (sin estado servidor)
- ¿El nombre del Pokémon ancla se valida contra el pool legal en el endpoint o se deja fallar a `team_generator`? → Validar en el endpoint, devolver 422 con mensaje claro si no está en el pool M-A
