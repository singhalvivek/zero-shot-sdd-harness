from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# src/api/__init__.py → 3 parents up = repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _ensure_dirs() -> None:
    for rel in (
        "artifacts",
        "artifacts/exports",
        "artifacts/code",
        "artifacts/previews",
        "generated_code",
        "data",
    ):
        (_REPO_ROOT / rel).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from db.session import init_db

    _ensure_dirs()
    init_db()
    # Warm the CadQuery/OCP import in a background thread so the first user
    # generation's sandbox child spawn hits a hot OS cache (fast, first-time-right)
    # without blocking startup (or slowing mock-based tests).
    import threading

    def _warm():
        try:
            from sandbox import warm_cadquery

            warm_cadquery()
        except Exception:  # noqa: BLE001 — warmup is best-effort, never fatal
            pass

    threading.Thread(target=_warm, name="cadquery-warmup", daemon=True).start()
    yield


def create_app() -> FastAPI:
    _ensure_dirs()
    app = FastAPI(title="AI CAD Studio", version="0.1.0", lifespan=_lifespan)

    from api import health, runs

    app.include_router(health.router)
    app.include_router(runs.router)

    # Read-only static artifacts (STL / STEP / code copy / preview PNG).
    artifacts_dir = _REPO_ROOT / "artifacts"
    app.mount(
        "/artifacts",
        StaticFiles(directory=str(artifacts_dir)),
        name="artifacts",
    )

    # Serve the built Next.js static export at /app (present after pnpm build).
    frontend_out = _REPO_ROOT / "frontend" / "out"
    if frontend_out.exists():
        app.mount(
            "/app",
            StaticFiles(directory=str(frontend_out), html=True),
            name="frontend",
        )

    return app


app = create_app()
