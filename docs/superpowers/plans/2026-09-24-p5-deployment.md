# P5 Deployment Implementation Plan

> **For agentic workers:** Execute this plan task-by-task. Do not commit or push until the test, container, application, and independent review gates pass.

**Goal:** Package the current repository as a reproducible P5 deployment baseline with a production Docker image, non-provisioning Compose configuration, centralized timestamped logging, a health endpoint, and a Render deployment descriptor.

**Architecture:** Add only the operational application shell required by P5: a minimal FastAPI process exposes `/health` and `/docs`; it does not implement P1 discussion/analytics routes or P2/P3 views. One Docker image runs the API. Compose starts that API by default and keeps the existing PostgreSQL service behind a `legacy-db` profile so a normal P5 run never pulls or creates a database. Render builds the same Dockerfile and checks `/health`.

**Tech Stack:** Python 3.11, FastAPI, Uvicorn, pytest, Docker, Docker Compose, Render Docker service.

**Scope:** P5 only. P1–P4 product features and P6 documentation/demo deliverables remain explicitly out of scope for this mission; their gaps are recorded in the final handoff.

## Global Constraints

- Never pull, create, reset, or delete MongoDB or PostgreSQL during P5 validation.
- Never start the `legacy-db` Compose profile during validation; use the existing PC database only if a later live smoke explicitly requires it.
- Never commit `.env`, API keys, database credentials, or cloud tokens.
- Preserve the existing PostgreSQL service definition and volume behind the `legacy-db` profile.
- Do not implement P1 CRUD routes, P2 discussion UI, P3 analytics UI, or P4 engine services in this plan.
- Do not commit or push until tests, Docker build/run, application smoke, and independent reviews pass.

---

### Task 1: Add failing P5 health and logging tests

**Files:**
- Create: `tests/test_deployment.py`
- Create: `pytest.ini`

**Interfaces:**
- Consumes: `src.api.main:app`, `src.utils.logger.configure_logging`.
- Produces: executable acceptance tests for the P5 health surface and test discovery.

- [ ] **Step 1: Write the failing tests**

Create tests that import the application, call `GET /health` and `GET /` through FastAPI's in-process `TestClient`, assert the exact health payload, assert the service metadata, and assert that health requests emit an INFO log containing `health_check`. Add `pytest.ini` with `testpaths = tests` and `python_files = test_*.py` so the interactive `scripts/test_agents.py` is not collected.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/test_deployment.py -q`

Expected: collection or import failure because `src.api` and `src.utils.logger` do not yet exist.

- [ ] **Step 3: Do not implement yet**

Keep the test file as the executable contract for Task 2. Do not add production code before the RED result is observed.

### Task 2: Implement the P5 runtime and logger

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/main.py`
- Create: `src/utils/__init__.py`
- Create: `src/utils/logger.py`
- Modify: `requirements.txt:1-13`

**Interfaces:**
- `src.api.main:app` — FastAPI application.
- `GET /health` — returns HTTP 200 with exactly `{"status": "ok"}`.
- `GET /` — returns service name, status, and docs path.
- `src.utils.logger.configure_logging(level: str | None = None) -> None` — idempotently configures timestamp, level, and stream output.

- [ ] **Step 1: Add the minimal application shell**

Create a FastAPI app with the two read-only endpoints above. Configure logging during startup, log health requests at INFO, and let FastAPI provide `/docs`. Do not add CORS, topic, discussion, or analytics routes.

- [ ] **Step 2: Add centralized logging**

Use the standard library logging module with a stable format containing ISO-8601 timestamp, level, logger name, and message. Read `LOG_LEVEL` from the environment with `INFO` as the default. Do not log secrets or request bodies.

- [ ] **Step 3: Add pinned-compatible runtime dependencies**

Add `fastapi>=0.115,<1` and `uvicorn[standard]>=0.30,<1` to `requirements.txt`. Keep the existing dependency list unchanged otherwise.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `python -m pytest tests/test_deployment.py -q`

Expected: all P5 health/logging tests pass with no live network or database access.

### Task 3: Add production container and deployment descriptors

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Modify: `docker-compose.yml:1-16`
- Create: `render.yaml`

**Interfaces:**
- Image default command: `uvicorn src.api.main:app --host 0.0.0.0 --port 8000`.
- Compose service: `api`, published as `${APP_PORT:-8000}:8000`.
- Legacy database service: `postgres`, profile `legacy-db`, not started by default.
- Render service: Docker runtime, public web service, health check `/health`.

- [ ] **Step 1: Write the production Dockerfile**

Use `python:3.11-slim`, install only `requirements.txt`, copy the application source, set unbuffered output, run as a non-root user, expose port 8000, add a stdlib-based health check, and start Uvicorn. Do not install a database client or database image in the Dockerfile.

- [ ] **Step 2: Write the build context exclusions**

Exclude `.git`, `.env`, virtual environments, caches, tests, local data, reports, and generated outputs from the image. Keep `src`, `requirements.txt`, and deployment metadata available to the build.

- [ ] **Step 3: Convert Compose to app-first mode**

Make `api` the only default service. Preserve the existing PostgreSQL service and volume under `profiles: [legacy-db]`; do not change its database name, credentials, port, volume name, or initialization SQL. Add `LOG_LEVEL` and `host.docker.internal` support for future explicitly enabled live retrieval, without starting that database service.

- [ ] **Step 4: Add Render deployment metadata**

Create a Docker web service with `healthCheckPath: /health`, port 8000, and only non-secret `LOG_LEVEL` configuration. Do not add a Render Postgres service or any secret value.

- [ ] **Step 5: Validate configuration without pulling images**

Run: `docker compose config` and `docker compose config --services`

Expected: `api` is the only default service; the legacy database is not started by the default P5 command. Do not run `docker compose up` with the `legacy-db` profile.

### Task 4: Verify tests, image, and application

**Files:**
- No source changes expected.

- [ ] **Step 1: Run the complete test suite**

Run: `python -m pytest -q`

Expected: collection is limited to `tests/`, all tests pass, and no live service is contacted. If the environment lacks a declared dependency, install from the existing `requirements.txt` only; do not provision a database.

- [ ] **Step 2: Build the image**

Run: `docker build -t football-analysis-rag:p5 .`

Expected: exit code 0 without creating or pulling a database image.

- [ ] **Step 3: Run the P5 container**

Run: `docker run --rm -p 8000:8000 -e LOG_LEVEL=INFO football-analysis-rag:p5`

Expected: Uvicorn binds `0.0.0.0:8000`; `GET /health` returns HTTP 200 and `{"status":"ok"}`; `/docs` is reachable; logs contain timestamp, level, and health event.

- [ ] **Step 4: Run Compose smoke without the database profile**

Run: `docker compose up --build -d api` followed by the same health and docs requests.

Expected: only the API service starts. The PostgreSQL service is not created or started.

### Task 5: Independent reviews and final application run

**Files:**
- Review the complete P5 diff; fix all Critical and Important findings before proceeding.

- [ ] **Step 1: Run an independent security review**

Review image safety, secret exposure, health endpoint behavior, Docker context exclusions, Compose profile isolation, and Render configuration. Fix all Critical and Important findings.

- [ ] **Step 2: Run an independent architecture review**

Review the app/UI boundary, database non-provisioning guarantee, deployment reproducibility, and P5/P6 boundary. Fix all Critical and Important findings.

- [ ] **Step 3: Run a final code review**

Review correctness, tests, configuration consistency, logging, and documentation of the P5 diff. Fix all Critical and Important findings.

- [ ] **Step 4: Run the final application smoke test**

Start the actual container through the managed process runner, request `/health`, `/`, and `/docs`, capture the timestamped health log, then stop the process cleanly. Do not claim completion unless these requests and the independent reviews have fresh evidence.

### Task 6: Commit and push only after approval gates

**Files:**
- Commit the reviewed P5 files and this plan.

- [ ] **Step 1: Inspect the final diff and status**

Confirm only P5 files changed and no `.env`, database dump, generated output, or unrelated user artifact is staged.

- [ ] **Step 2: Create one reviewable commit**

Run: `git add Dockerfile .dockerignore docker-compose.yml render.yaml requirements.txt pytest.ini src/api src/utils tests/test_deployment.py docs/superpowers/plans/2026-09-24-p5-deployment.md` then commit with `feat: add P5 deployment baseline`.

- [ ] **Step 3: Push the reviewed commit**

Run: `git push origin main`

Expected: push succeeds and the remote branch contains the reviewed commit. Do not push if any test, review, or smoke gate is failing.

### Task 7: P6 handoff record

- [ ] **Step 1: Report remaining P1–P4 and P6 work**

Record that P1 routes, P2 discussion UI, P3 analytics UI, P4 service integration, `DEPLOYMENT.md`, README refresh, `tests/test_api.py`, and the final demo video remain future work. Do not claim those deliverables are complete in this P5-only mission.
