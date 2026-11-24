"""Configurar el cliente de IA del Proyecto II desde el entorno, igual que su CLI."""

from __future__ import annotations

import os
from collections.abc import Mapping

from swarmtrade_app.ai_client import AIClient, AIClientError, AIResponse, AnalysisRequest

# >> Tema 4, B2 y B9: modos de fallo del mock para provocar cada rama sin red ni clave.
#    AI_MOCK_MODE -> kind de AIClientError (el III lo traduce a 503, 504 o 502); «bug» => excepción propia (500).
MOCK_FAULTS = {"down": "unavailable", "timeout": "timeout", "invalid": "invalid_response", "bug": None}


class FailingMock:
    """> Mock que falla siempre del modo pedido. El motivo solo llega al log, nunca a la respuesta."""

    provider = "mock"
    secret_env = None

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.model = f"mock-fallo-{mode}"

    def analyze(self, request: AnalysisRequest) -> AIResponse:
        kind = MOCK_FAULTS[self.mode]
        if kind is None:
            raise RuntimeError("fallo simulado del mock (AI_MOCK_MODE=bug)")
        raise AIClientError(f"Fallo simulado del mock (AI_MOCK_MODE={self.mode})", kind=kind)


def client_from_env(provider: str | None = None, env: Mapping[str, str] | None = None) -> AIClient | FailingMock:
    """Envoltorio fino de ``AIClient.from_env``: mismas variables y mensajes que la CLI del II.

    ``provider`` (mock, hf o nvidia), si se indica, sustituye a ``AI_PROVIDER``. Las claves nunca
    pasan por aquí: el cliente lee ``HF_TOKEN`` o ``NVIDIA_API_KEY`` solo al llamar al proveedor.
    ``AI_MOCK_MODE`` (down, timeout, invalid o bug) solo actúa con el mock; con un proveedor real
    se ignora, así que en Render no cambia nada.
    """
    env = os.environ if env is None else env
    if provider:
        env = {**env, "AI_PROVIDER": provider}
    client = AIClient.from_env(env)
    mode = str(env.get("AI_MOCK_MODE") or "").strip().lower()
    if not mode or client.provider != "mock":
        return client
    if mode not in MOCK_FAULTS:
        raise AIClientError("AI_MOCK_MODE debe ser down, timeout, invalid o bug", kind="config")
    return FailingMock(mode)
