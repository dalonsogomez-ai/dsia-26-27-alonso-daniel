"""-> Paquete para cargar, validar y analizar ventas."""

from .loader import (
    CsvSalesRepository,
    DataLoadError,
    JsonSalesRepository,
    SalesRepository,
    load,
    load_from,
)
from .validator import ValidationError, validate_sales

__all__ = [
    "CsvSalesRepository",
    "DataLoadError",
    "JsonSalesRepository",
    "SalesRepository",
    "ValidationError",
    "load",
    "load_from",
    "validate_sales",
]
