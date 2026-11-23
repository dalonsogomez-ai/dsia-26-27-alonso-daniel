"""Contrato versionado del informe compartido por el CLI, la API y el dashboard."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
ModelName = Literal["dummy", "ridge", "swarm"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Metrics(Contract):
    rmse: Annotated[FiniteFloat, Field(ge=0)]
    mae: Annotated[FiniteFloat, Field(ge=0)]
    r2: FiniteFloat
    sign_accuracy: Annotated[FiniteFloat, Field(ge=0, le=1)]


class Period(Contract):
    start: date
    end: date
    max_target_end: date
    rows: Annotated[int, Field(gt=0)]
    dates: Annotated[int, Field(gt=0)]

    @model_validator(mode="after")
    def validate_order(self) -> Period:
        if not self.start <= self.end < self.max_target_end or self.dates > self.rows:
            raise ValueError("Periodo de evaluación incoherente")
        return self


class Prediction(Contract):
    symbol: Annotated[str, Field(min_length=1, max_length=32)]
    predicted_return: FiniteFloat


class InputSummary(Contract):
    """Resumen por símbolo de las barras de entrada hasta ``as_of`` para explorar los datos."""

    symbol: Annotated[str, Field(min_length=1, max_length=32)]
    sessions: Annotated[int, Field(gt=0, description="Sesiones con barra en el CSV")]
    last_close: Annotated[FiniteFloat, Field(gt=0, description="Último cierre")]
    return_21_sessions: Annotated[FiniteFloat | None, Field(
        description="Retorno realizado de las últimas 21 sesiones")] = None
    volatility_annualized: Annotated[FiniteFloat | None, Field(
        ge=0, description="Desviación típica de los últimos 63 retornos diarios × √252")] = None


class Explanation(Contract):
    provider: Literal["mock", "huggingface"]
    task: Literal["chat_completion"]
    model: str
    text: str


class Snapshot(Contract):
    schema_version: Literal[1] = 1
    run_id: Hash
    generated_at: datetime
    as_of: date
    data_kind: Literal["synthetic", "alpaca", "local"]
    input_sha256: Hash
    artifact_sha256: Hash
    sklearn_version: str
    target_id: Literal["return_21_sessions"] = "return_21_sessions"
    horizon_sessions: Literal[21] = 21
    model: ModelName
    validation: dict[ModelName, Metrics]
    holdout: Metrics
    splits: dict[Literal["train", "validation", "test"], Period]
    holdout_touches: Literal[1] = 1
    predictions: Annotated[list[Prediction], Field(min_length=5)]
    evidence: Literal["advantage_not_demonstrated"] = "advantage_not_demonstrated"
    explanation: Explanation | None = None
    # > Campo opcional añadido tras la RC1: los snapshots previos siguen validando con su run_id.
    input_summary: list[InputSummary] | None = None

    def content_digest(self) -> str:
        excluded = {"run_id"} if self.input_summary is not None else {"run_id", "input_summary"}
        document = self.model_dump(mode="json", exclude=excluded)
        raw = json.dumps(document, sort_keys=True, allow_nan=False, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def validate_consistency(self) -> Snapshot:
        if set(self.validation) != {"dummy", "ridge", "swarm"}:
            raise ValueError("Faltan candidatos del contrato de validación")
        if set(self.splits) != {"train", "validation", "test"}:
            raise ValueError("Faltan cortes cronológicos")
        train, validation, test = (self.splits[name] for name in ("train", "validation", "test"))
        if not train.max_target_end < validation.start or not validation.max_target_end < test.start:
            raise ValueError("Las etiquetas cruzan las fronteras del split")
        if test.max_target_end > self.as_of:
            raise ValueError("El holdout contiene etiquetas posteriores a la fecha de corte")
        if len({item.symbol for item in self.predictions}) != len(self.predictions):
            raise ValueError("Símbolos duplicados en las predicciones")
        if self.input_summary is not None and (
                sorted(item.symbol for item in self.input_summary)
                != sorted(item.symbol for item in self.predictions)):
            raise ValueError("El resumen de entrada no cubre exactamente los símbolos predichos")
        if self.generated_at.tzinfo is None or self.generated_at.date() < self.as_of:
            raise ValueError("Fecha de generación incompatible")
        if self.run_id != self.content_digest():
            raise ValueError("El hash del informe no coincide")
        return self


def create_snapshot(payload: dict) -> Snapshot:
    """Calcular el identificador sobre los datos ya normalizados y validar su contenido."""
    normalized = Snapshot.model_construct(run_id="0" * 64, **payload)
    values = normalized.model_dump(warnings="error")
    values["run_id"] = normalized.content_digest()
    return Snapshot.model_validate(values)


def read_snapshot(path: Path) -> Snapshot:
    with path.open("rb") as stream:
        data = stream.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("El snapshot supera el límite de lectura")
    return Snapshot.model_validate_json(data)
