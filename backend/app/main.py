"""Ponto de entrada ASGI do EduVigIA.

A aplicação principal foi movida para ``app.application``. Isso mantém o
comando Uvicorn estável enquanto permite separar progressivamente os módulos.
"""
from app.core.logging import configure_logging

configure_logging()

from app.application import app  # noqa: E402,F401
