"""Configurar el cliente de IA del Proyecto II desde el entorno, igual que su CLI."""

from __future__ import annotations

import os
from collections.abc import Mapping

from swarmtrade_app.ai_client import AIClient, AIClientError

DEFAULT_PROVIDER = "mock"


def client_from_env(provider: str | None = None, env: Mapping[str, str] | None = None) -> AIClient:
    """Crear un ``AIClient`` con ``AI_PROVIDER``, ``HF_MODEL``, ``HF_TIMEOUT`` y ``HF_INFERENCE_PROVIDER``.

    El token nunca pasa por aquí: el cliente lo lee de ``HF_TOKEN`` solo al llamar al proveedor.
    """
    env = os.environ if env is None else env
    chosen = provider or env.get("AI_PROVIDER", "").strip() or DEFAULT_PROVIDER
    try:
        timeout = float(env.get("HF_TIMEOUT", "").strip() or 30)
        max_tokens = int(env.get("HF_MAX_TOKENS", "").strip() or 256)
    except ValueError:
        raise AIClientError("HF_TIMEOUT o HF_MAX_TOKENS no son números válidos") from None
    return AIClient(chosen, env.get("HF_MODEL", "").strip() or None, timeout=timeout,
                    max_tokens=max_tokens,
                    inference_provider=env.get("HF_INFERENCE_PROVIDER", "").strip() or "auto")
