"""Backward-compatible re-export of the FastAPI app.

The real definition lives in `systema2.api`. `main.py` and uvicorn's
``systema2.app:app`` reload string keep working through this module.
"""

from systema2.api import app

__all__ = ["app"]
