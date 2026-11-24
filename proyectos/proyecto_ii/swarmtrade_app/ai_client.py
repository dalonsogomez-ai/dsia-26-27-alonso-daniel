"""-> Cliente tipado mock/HF/NVIDIA siguiendo el ejemplo de clase ai_api_client.py."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import MISSING, dataclass, fields
from datetime import date
import json
import logging
import math
import numbers
import os
import random
import re
import time
from time import perf_counter

LOG = logging.getLogger(__name__)

DEFAULT_HF_MODEL = 'Qwen/Qwen2.5-7B-Instruct'
# -> NVIDIA (build.nvidia.com): API compatible con OpenAI; alternativa a HF cuando la cuenta HF no tiene saldo.
DEFAULT_NVIDIA_MODEL = 'moonshotai/kimi-k3.1-pro'
NVIDIA_BASE_URL = 'https://integrate.api.nvidia.com/v1'
NVIDIA_REASONING_EFFORT = 'low'
# > Reintentos solo para fallos transitorios (429, 5xx, timeouts, conexión): 0,5 s y 1 s con jitter.
MAX_RETRIES = 2
BACKOFF_SECONDS = 0.5
JITTER_SECONDS = 0.1
MAX_TIMEOUT_SECONDS = 120
DATA_KINDS = frozenset({'synthetic', 'alpaca', 'local'})
GENERIC_FAILURE = 'Inferencia HF fallida; comprueba red, permisos, saldo y modelo/proveedor'
FATAL_STATUS = {401: 'Token de Hugging Face inválido o sin permisos',
                403: 'Token de Hugging Face inválido o sin permisos',
                404: 'Modelo o proveedor de inferencia no disponible'}
NVIDIA_GENERIC_FAILURE = 'Inferencia NVIDIA fallida; comprueba red, clave, cuota y modelo'
NVIDIA_FATAL_STATUS = {401: 'Clave de NVIDIA inválida o sin permisos',
                       403: 'Clave de NVIDIA inválida o sin permisos',
                       404: 'Modelo de NVIDIA no disponible'}
_MODEL_ID = re.compile(r'[A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*')
_INFERENCE_PROVIDER = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')


class AIClientError(RuntimeError):
    """Error externo redactado: nunca incorpora claves ni el cuerpo del servidor."""


class _NoFinalAnswer(ValueError):
    """> NVIDIA respondió sin message.content útil: no se reintenta porque repetir no lo arregla."""


@dataclass(frozen=True)
class _Provider:
    """> Lo que cambia entre proveedores reales; reintentos, redacción y payload son comunes."""
    name: str  # > En logs y en AIResponse.provider.
    secret_env: str
    fatal_status: Mapping[int, str]
    generic_failure: str
    timeout: float
    max_tokens: int
    max_tokens_limit: int


# >> Los modelos de razonamiento de NVIDIA gastan tokens antes de la respuesta: más salida y más tiempo.
# mock comparte los límites de HF para no cambiar el comportamiento previo.
_PROVIDERS = {'hf': _Provider('huggingface', 'HF_TOKEN', FATAL_STATUS, GENERIC_FAILURE, 30, 256, 512),
              'nvidia': _Provider('nvidia', 'NVIDIA_API_KEY', NVIDIA_FATAL_STATUS, NVIDIA_GENERIC_FAILURE,
                                  60, 1024, 4096)}


def provider_name(value: str) -> str:
    """> Normaliza el proveedor como la demo de clase: 'huggingface' es alias de 'hf'."""
    name = str(value).lower().strip()
    return 'hf' if name == 'huggingface' else name


def _is_int(value) -> bool:
    return isinstance(value, numbers.Integral) and not isinstance(value, bool)


def _is_finite(value) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(value)


@dataclass(frozen=True)
class AnalysisRequest:
    """Resumen agregado que viaja a la IA.

    Los 14 factores son z-scores cross-section por fecha, así que la media diaria de las
    predicciones (``mean_prediction``) es constante e igual a la media del target en train: el
    modelo aporta el orden relativo entre símbolos. Por eso se añaden la dispersión
    (``prediction_std``), el rango (``prediction_spread`` = máximo − mínimo) y la mejor señal
    (``top_symbol``). Son opcionales para seguir leyendo informes anteriores.
    """
    as_of: str
    model: str
    horizon: int
    symbols: int
    mean_prediction: float
    validation_rmse: float
    data_kind: str
    prediction_std: float | None = None
    prediction_spread: float | None = None
    top_symbol: str | None = None

    def __post_init__(self):
        problem = self._problem()
        if problem:
            raise AIClientError(f'Resumen para la IA no válido: {problem}')

    def _problem(self) -> str | None:
        try:
            date.fromisoformat(self.as_of)
        except (TypeError, ValueError):
            return 'as_of debe ser una fecha ISO (AAAA-MM-DD)'
        if not isinstance(self.model, str) or not self.model.strip():
            return 'model debe ser un texto no vacío'
        for name in ('horizon', 'symbols'):
            value = getattr(self, name)
            if not _is_int(value) or value <= 0:
                return f'{name} debe ser un entero mayor que 0'
        if not _is_finite(self.mean_prediction):
            return 'mean_prediction debe ser un número finito'
        for name in ('validation_rmse', 'prediction_std', 'prediction_spread'):
            value = getattr(self, name)
            if value is None and name != 'validation_rmse':
                continue
            if not _is_finite(value) or value < 0:
                return f'{name} debe ser un número finito mayor o igual que 0'
        if self.top_symbol is not None and (not isinstance(self.top_symbol, str) or not self.top_symbol.strip()):
            return 'top_symbol debe ser un texto no vacío'
        if self.data_kind not in DATA_KINDS:
            return 'data_kind debe ser synthetic, alpaca o local'
        return None

    @classmethod
    def from_dict(cls, data) -> AnalysisRequest:
        """> Construye el resumen desde JSON con errores de dominio para claves sobrantes o ausentes."""
        if not isinstance(data, dict):
            raise AIClientError('Resumen para la IA no válido: se espera un objeto JSON')
        known = {f.name for f in fields(cls)}
        required = {f.name for f in fields(cls) if f.default is MISSING}
        extra, missing = sorted(set(data) - known), sorted(required - set(data))
        if extra:
            raise AIClientError(f'Resumen para la IA no válido: claves sobrantes: {", ".join(extra)}')
        if missing:
            raise AIClientError(f'Resumen para la IA no válido: faltan claves: {", ".join(missing)}')
        return cls(**data)


@dataclass(frozen=True)
class AIResponse:
    provider: str
    task: str
    model: str
    text: str


def _env_number(env: Mapping[str, str], name: str, default: str, cast: type, low: float, high: float):
    """> Lee un límite numérico del entorno con un error de dominio en lugar del de Python."""
    raw = str(env.get(name) or '').strip() or default
    try:
        value = cast(raw)
    except ValueError:
        value = None
    if value is None or not low <= value <= high:
        raise AIClientError(f'{name} debe ser un número entre {low:g} y {high:g}')
    return value


def _status_code(exc: BaseException) -> int | None:
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    return status if isinstance(status, int) else None


def _is_transient(exc: BaseException, status: int | None) -> bool:
    if status is not None:
        return status == 429 or status >= 500
    import httpx
    # > InferenceTimeoutError hereda de TimeoutError; httpx.TransportError cubre conexión y timeouts de httpx.
    return isinstance(exc, (TimeoutError, ConnectionError, httpx.TransportError))


class AIClient:
    def __init__(self, provider: str = 'mock', model: str | None = None,
                 timeout: float | None = None, max_tokens: int | None = None, inference_provider: str = 'auto',
                 sleep: Callable[[float], None] = time.sleep):
        provider = provider_name(provider)  # > 'huggingface' es alias de 'hf', como en la demo de clase.
        if provider not in {'mock', 'hf', 'nvidia'}:
            raise AIClientError('Proveedor no soportado; usa mock, hf o nvidia')
        spec = _PROVIDERS.get(provider, _PROVIDERS['hf'])
        timeout = spec.timeout if timeout is None else timeout
        max_tokens = spec.max_tokens if max_tokens is None else max_tokens
        if not 1 <= timeout <= MAX_TIMEOUT_SECONDS or not 1 <= max_tokens <= spec.max_tokens_limit:
            raise AIClientError('Límites de tiempo o tokens no válidos')
        self.provider = provider
        self.model = model or (DEFAULT_NVIDIA_MODEL if provider == 'nvidia' else DEFAULT_HF_MODEL)
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.inference_provider = inference_provider
        self._sleep = sleep  # > Inyectable: las pruebas registran las esperas sin dormir.

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> AIClient:
        """Crea el cliente desde ``AI_PROVIDER``, ``HF_*`` y ``NVIDIA_*``; la CLI del II y el III lo comparten.

        Las variables vacías equivalen a no definidas. Se validan todas aunque su proveedor no esté
        activo: un valor erróneo se detecta al arrancar, no al cambiar ``AI_PROVIDER``. Con
        ``AI_PROVIDER=nvidia`` el modelo y los límites salen de ``NVIDIA_*`` (sus valores por defecto
        difieren de los de HF). Las claves no pasan por aquí: ``analyze`` lee ``HF_TOKEN`` o
        ``NVIDIA_API_KEY`` solo al llamar al proveedor.
        """
        env = os.environ if environ is None else environ

        def read(name: str, default: str) -> str:
            return str(env.get(name) or '').strip() or default

        def model_id(name: str, default: str) -> str:
            model = read(name, default)
            if not _MODEL_ID.fullmatch(model):
                raise AIClientError(f'{name} debe tener el formato propietario/nombre, p. ej. {default}')
            return model

        model = model_id('HF_MODEL', DEFAULT_HF_MODEL)
        timeout = _env_number(env, 'HF_TIMEOUT', '30', float, 1, MAX_TIMEOUT_SECONDS)
        max_tokens = _env_number(env, 'HF_MAX_TOKENS', '256', int, 1, _PROVIDERS['hf'].max_tokens_limit)
        inference_provider = read('HF_INFERENCE_PROVIDER', 'auto')
        if not _INFERENCE_PROVIDER.fullmatch(inference_provider):
            raise AIClientError('HF_INFERENCE_PROVIDER debe ser auto o un identificador en minúsculas con guiones')
        nvidia = _PROVIDERS['nvidia']
        nvidia_model = model_id('NVIDIA_MODEL', DEFAULT_NVIDIA_MODEL)
        nvidia_timeout = _env_number(env, 'NVIDIA_TIMEOUT', f'{nvidia.timeout:g}', float, 1, MAX_TIMEOUT_SECONDS)
        nvidia_tokens = _env_number(env, 'NVIDIA_MAX_TOKENS', str(nvidia.max_tokens), int, 1, nvidia.max_tokens_limit)
        provider = read('AI_PROVIDER', 'mock')
        if provider_name(provider) == 'nvidia':
            model, timeout, max_tokens = nvidia_model, nvidia_timeout, nvidia_tokens
        return cls(provider, model, timeout=timeout, max_tokens=max_tokens, inference_provider=inference_provider)

    def analyze(self, request: AnalysisRequest) -> AIResponse:
        if self.provider == 'mock':
            LOG.info('IA provider=mock model=mock-determinista-v1 latency_ms=0 ai_status=completed')
            return AIResponse('mock', 'chat_completion', 'mock-determinista-v1', self._mock_text(request))
        spec = _PROVIDERS[self.provider]
        token = os.environ.get(spec.secret_env, '').strip()
        if not token:
            raise AIClientError(f'Falta {spec.secret_env} en el entorno')
        # > Solo se envían agregados: ni precios ni datos crudos; como mucho, el ticker de la mejor señal.
        payload = {'date': request.as_of, 'model': request.model, 'horizon_sessions': request.horizon,
                   'n_symbols': request.symbols, 'mean_prediction': request.mean_prediction,
                   'validation_rmse': request.validation_rmse, 'data_kind': request.data_kind}
        payload.update({name: getattr(request, name) for name in ('prediction_std', 'prediction_spread', 'top_symbol')
                        if getattr(request, name) is not None})
        messages = [{'role': 'system', 'content': 'Explica en español este experimento académico. '
                     'Usa solo las cifras suministradas. Distingue error predictivo y rentabilidad. '
                     'La media diaria de las predicciones es casi constante porque los factores son z-scores por '
                     'fecha: interpreta la dispersión, el rango y la mejor señal como el orden relativo entre '
                     'símbolos. Indica si los datos son sintéticos. No sugieras órdenes ni pesos.'},
                    {'role': 'user', 'content': json.dumps(payload, allow_nan=False)}]
        chat = self._chat_nvidia if self.provider == 'nvidia' else self._chat
        where = (f'provider={spec.name}' if self.provider == 'nvidia'
                 else f'provider={spec.name} inference_provider={self.inference_provider}')
        attempt = 0
        while True:
            attempt += 1
            # > Nunca se registra el token: solo proveedor, modelo, latencia, estado, intento y tipo de error.
            start = perf_counter()
            try:
                text = chat(token, messages)
            except Exception as exc:
                status = _status_code(exc)
                LOG.warning('IA %s model=%s latency_ms=%.0f ai_status=failed error_type=%s status=%s attempt=%d',
                            where, self.model, (perf_counter() - start) * 1000, type(exc).__name__,
                            status or '-', attempt)
                if isinstance(exc, _NoFinalAnswer):
                    raise AIClientError(str(exc)) from None
                if status in spec.fatal_status:
                    raise AIClientError(spec.fatal_status[status]) from None
                if attempt > MAX_RETRIES or not _is_transient(exc, status):
                    raise AIClientError(spec.generic_failure) from None
                delay = BACKOFF_SECONDS * 2 ** (attempt - 1) + random.uniform(0, JITTER_SECONDS)
                LOG.info('IA provider=%s reintento=%d espera_s=%.2f', spec.name, attempt, delay)
                self._sleep(delay)
                continue
            LOG.info('IA %s model=%s latency_ms=%.0f ai_status=completed attempt=%d',
                     where, self.model, (perf_counter() - start) * 1000, attempt)
            return AIResponse(spec.name, 'chat_completion', self.model, text.replace(token, '[REDACTED]'))

    def _chat_nvidia(self, key: str, messages: list[dict]) -> str:
        # > Transporte: el mismo InferenceClient de HF con base_url. En huggingface_hub 1.33.0 una URL
        # usa el helper hf-inference, que añade /chat/completions, envía Authorization: Bearer <clave>
        # y fusiona extra_body en el JSON; así se reutilizan sus errores HTTP y no hay dependencia nueva.
        from huggingface_hub import InferenceClient
        client = InferenceClient(base_url=NVIDIA_BASE_URL, api_key=key, timeout=self.timeout)
        result = client.chat_completion(model=self.model, max_tokens=self.max_tokens, temperature=0.1,
                                        messages=messages, extra_body={'reasoning_effort': NVIDIA_REASONING_EFFORT})
        choices = getattr(result, 'choices', None) or []
        message = getattr(choices[0], 'message', None) if choices else None
        text = getattr(message, 'content', None)
        if isinstance(text, str) and text.strip():
            return text
        # > ChatCompletionOutputMessage expone también los campos fuera de su esquema como atributos.
        if getattr(message, 'reasoning_content', None) or getattr(message, 'reasoning', None):
            raise _NoFinalAnswer('NVIDIA devolvió solo razonamiento, sin respuesta final; aumenta NVIDIA_MAX_TOKENS')
        raise _NoFinalAnswer('NVIDIA devolvió una respuesta vacía')

    def _chat(self, token: str, messages: list[dict]) -> str:
        from huggingface_hub import InferenceClient
        client = InferenceClient(api_key=token, provider=self.inference_provider, timeout=self.timeout)
        result = client.chat_completion(model=self.model, max_tokens=self.max_tokens, temperature=0.1,
                                        messages=messages)
        text = result.choices[0].message.content
        if not isinstance(text, str) or not text.strip():
            raise ValueError('Respuesta vacía')
        return text

    @staticmethod
    def _mock_text(request: AnalysisRequest) -> str:
        parts = [f'[mock] Modelo {request.model}', f'horizonte {request.horizon} sesiones',
                 f'{request.symbols} símbolos', f'media predicha {request.mean_prediction:.4%}']
        if request.prediction_std is not None:
            parts.append(f'dispersión entre símbolos {request.prediction_std:.4%}')
        if request.prediction_spread is not None:
            parts.append(f'rango de predicciones {request.prediction_spread:.4%}')
        if request.top_symbol is not None:
            parts.append(f'mejor señal {request.top_symbol}')
        parts.append(f'RMSE validación {request.validation_rmse:.6f}')
        return '; '.join(parts) + '. La predicción no demuestra rentabilidad ni incluye costes de ejecución.'
