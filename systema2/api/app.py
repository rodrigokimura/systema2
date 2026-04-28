from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from systema2.api.auth import require_api_key
from systema2.api.routes import projects as projects_routes
from systema2.api.routes import tasks as tasks_routes
from systema2.database import engine, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield
    engine.dispose()


app = FastAPI(title="systema2", lifespan=lifespan)


@app.get("/")
def root() -> dict[str, str]:
    return {"app": "systema2", "status": "ok"}


# Protect the data-mutating/reading routers behind the API-key
# dependency. The ``/`` health endpoint above is intentionally left
# unauthenticated so reverse proxies / probes can hit it.
_auth = [Depends(require_api_key)]
app.include_router(projects_routes.router, dependencies=_auth)
app.include_router(tasks_routes.router, dependencies=_auth)
