"""Configurar el cliente de IA del Proyecto II desde el entorno, igual que su CLI."""

from __future__ import annotations

import os
from collections.abc import Mapping

from swarmtrade_app.ai_client import AIClient


def client_from_env(provider: str | None = None, env: Mapping[str, str] | None = None) -> AIClient:
    """Envoltorio fino de ``AIClient.from_env``: mismas variables y mensajes que la CLI del II.

    ``provider`` (mock, hf o nvidia), si se indica, sustituye a ``AI_PROVIDER``. Las claves nunca
    pasan por aquí: el cliente lee ``HF_TOKEN`` o ``NVIDIA_API_KEY`` solo al llamar al proveedor.
    """
    env = os.environ if env is None else env
    if provider:
        env = {**env, "AI_PROVIDER": provider}
    return AIClient.from_env(env)
