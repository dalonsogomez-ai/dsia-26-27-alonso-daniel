# -> Imagen del Proyecto III: API Starlette + dashboard, con el snapshot demo generado en el build.
# Contexto = raíz del repositorio:
#   docker build -f proyectos/proyecto_iii/Dockerfile -t dsia-iii .
#   docker run --rm -p 8000:8000 dsia-iii
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLBACKEND=Agg

WORKDIR /app

# > Solo las dependencias de ejecución, con las mismas versiones fijadas del II (sin marimo, pytest ni alpaca-py),
#   en una capa propia para reutilizar la caché entre builds.
COPY proyectos/proyecto_iii/requirements-runtime.txt proyectos/proyecto_iii/requirements-runtime.txt
RUN python -m pip install --no-cache-dir -r proyectos/proyecto_iii/requirements-runtime.txt

COPY proyectos/proyecto_ii proyectos/proyecto_ii
COPY proyectos/proyecto_iii proyectos/proyecto_iii

RUN useradd --create-home --uid 10001 dsia \
    && mkdir -p /app/runs \
    && chown dsia:dsia /app/runs

ENV PYTHONPATH=/app/proyectos/proyecto_ii:/app/proyectos/proyecto_iii \
    DSIA_SNAPSHOT=/app/runs/dsia-demo/snapshot.json \
    DSIA_JOURNAL=/app/runs/dsia-evidence/pipeline.jsonl \
    AI_PROVIDER=mock \
    PORT=8000

USER dsia

# >> Snapshot sintético reproducible (680 sesiones, 8 símbolos, semilla 42): sin datos de Alpaca.
RUN python -m dsia_web.build demo --work runs/dsia-demo/work \
      --output runs/dsia-demo/snapshot.json --journal runs/dsia-evidence/pipeline.jsonl

EXPOSE 8000

# ~> Sin curl en la imagen slim: la comprobación usa la biblioteca estándar. 503 => no sano.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'), timeout=4)"]

CMD ["sh", "-c", "exec uvicorn dsia_web.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
