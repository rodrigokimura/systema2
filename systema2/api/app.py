from contextlib import asynccontextmanager

from fastapi import FastAPI

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


app.include_router(tasks_routes.router)
