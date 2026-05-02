## ADDED Requirements

### Requirement: Service runs in a Docker container
The application SHALL be packaged as a Docker image that can be built and run with
standard `docker build` + `docker run` commands without any host Python installation.

#### Scenario: Docker build succeeds from repo root
- **WHEN** `docker build -t poke-builder .` is run from the repo root
- **THEN** the build completes without errors

#### Scenario: Container serves the API on configured port
- **WHEN** the container is started with `docker run -p 8000:8000 poke-builder`
- **THEN** `GET http://localhost:8000/health` returns 200

### Requirement: PORT is configurable via environment variable
The listening port SHALL be read from the `PORT` environment variable (required by
Railway and Render), falling back to `8000` if not set.

#### Scenario: Custom PORT is respected
- **WHEN** the container is started with `PORT=9000`
- **THEN** the service listens on port 9000

### Requirement: Static frontend is served by the same process
The FastAPI app SHALL serve the frontend static files at `/` so that a single
deployment URL covers both the API and the UI (no separate CDN needed for v1).

#### Scenario: Root path returns the HTML frontend
- **WHEN** `GET /` is requested
- **THEN** response is `text/html` and contains the UI markup

### Requirement: Deploy to Railway with zero manual config
A `railway.toml` or auto-detected Dockerfile SHALL allow one-click deploy from the
GitHub repo to Railway with no extra CLI setup steps.

#### Scenario: Railway deploy succeeds from GitHub
- **WHEN** the repo is connected to Railway and a deploy is triggered
- **THEN** the service starts, health check passes, and the public URL serves the UI
