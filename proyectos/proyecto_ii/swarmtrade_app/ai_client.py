"""-> Cliente tipado mock/HF siguiendo el ejemplo de clase ai_api_client.py."""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass


class AIClientError(RuntimeError):
    """Error externo redactado: nunca incorpora claves ni el cuerpo del servidor."""


@dataclass(frozen=True)
class AnalysisRequest:
    as_of: str
    model: str
    horizon: int
    symbols: int
    mean_prediction: float
    validation_rmse: float
    data_kind: str


@dataclass(frozen=True)
class AIResponse:
    provider: str
    task: str
    model: str
    text: str


class AIClient:
    def __init__(self, provider: str = 'mock', model: str | None = None,
                 timeout: float = 30, max_tokens: int = 256, inference_provider: str = 'auto'):
        if provider not in {'mock', 'hf'}:
            raise AIClientError('Proveedor no soportado; usa mock o hf')
        if not 1 <= timeout <= 120 or not 1 <= max_tokens <= 512:
            raise AIClientError('Límites de tiempo o tokens no válidos')
        self.provider = provider
        self.model = model or 'Qwen/Qwen2.5-7B-Instruct'
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.inference_provider = inference_provider

    def analyze(self, request: AnalysisRequest) -> AIResponse:
        if not all(math.isfinite(v) for v in (request.mean_prediction, request.validation_rmse)):
            raise AIClientError('Resumen con valores no finitos')
        if self.provider == 'mock':
            return AIResponse('mock', 'chat_completion', 'mock-determinista-v1',
                              f'[mock] Modelo {request.model}; horizonte {request.horizon} sesiones; '
                              f'{request.symbols} símbolos; media predicha {request.mean_prediction:.4%}; '
                              f'RMSE validación {request.validation_rmse:.6f}. '
                              'La predicción no demuestra rentabilidad ni incluye costes de ejecución.')
        token = os.environ.get('HF_TOKEN', '').strip()
        if not token:
            raise AIClientError('Falta HF_TOKEN en el entorno')
        # > Solo se envían agregados; los datos crudos y símbolos permanecen locales.
        payload = {'date': request.as_of, 'model': request.model, 'horizon_sessions': request.horizon,
                   'n_symbols': request.symbols, 'mean_prediction': request.mean_prediction,
                   'validation_rmse': request.validation_rmse, 'data_kind': request.data_kind}
        try:
            from huggingface_hub import InferenceClient
            client = InferenceClient(api_key=token, provider=self.inference_provider, timeout=self.timeout)
            result = client.chat_completion(model=self.model, max_tokens=self.max_tokens, temperature=0.1,
                messages=[{'role': 'system', 'content': 'Explica en español este experimento académico. '
                           'Usa solo las cifras suministradas. Distingue error predictivo y rentabilidad. '
                           'Indica si los datos son sintéticos. No sugieras órdenes ni pesos.'},
                          {'role': 'user', 'content': json.dumps(payload, allow_nan=False)}])
            text = result.choices[0].message.content
            if not isinstance(text, str) or not text.strip():
                raise ValueError('Respuesta vacía')
            return AIResponse('huggingface', 'chat_completion', self.model, text.replace(token, '[REDACTED]'))
        except Exception:
            raise AIClientError('Inferencia HF fallida; comprueba red, permisos, saldo y modelo/proveedor') from None
