"""Ponto central para a evolução de autenticação e criptografia.

A implementação legada permanece funcional em ``app.application`` nesta fase.
As próximas versões moverão os algoritmos para este módulo sem alterar a API.
"""
from __future__ import annotations


def mask_secret(value: str | None) -> str | None:
    if not value:
        return value
    return "********"
