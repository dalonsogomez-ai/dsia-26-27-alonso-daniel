""">> El runtime de la imagen usa exactamente las versiones fijadas del II."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", re.MULTILINE)


def pins(path: Path) -> dict[str, str]:
    return {name.lower().replace("_", "-"): version for name, version in PIN.findall(path.read_text())}


def test_runtime_requirements_are_a_subset_of_project_ii_pins():
    runtime = pins(ROOT / "proyectos/proyecto_iii/requirements-runtime.txt")
    shared = pins(ROOT / "proyectos/proyecto_ii/requirements.txt")
    # Arrange/Act: dependencias que el lote demo, la API y el cliente de IA necesitan en la imagen.
    for needed in ("scikit-learn", "starlette", "uvicorn", "pydantic", "huggingface-hub", "pandas", "alpaca-py"):
        assert needed in runtime, needed
    # Assert: ninguna versión nueva ni distinta respecto al entorno probado del II y el III.
    assert {name: version for name, version in runtime.items() if shared.get(name) != version} == {}
    assert not {"marimo", "pytest", "pytest-cov"} & runtime.keys()


def test_dockerfile_installs_the_runtime_requirements():
    dockerfile = (ROOT / "proyectos/proyecto_iii/Dockerfile").read_text()
    assert "pip install --no-cache-dir -r proyectos/proyecto_iii/requirements-runtime.txt" in dockerfile


def test_alpaca_keys_reach_the_build_only_as_a_secret_mount():
    dockerfile = (ROOT / "proyectos/proyecto_iii/Dockerfile").read_text()
    dockerignore = (ROOT / ".dockerignore").read_text().split()
    # Assert: secreto montado solo en el RUN del lote; nunca ARG/ENV con claves; fuera del contexto COPY.
    assert dockerfile.startswith("# syntax=docker/dockerfile:1")
    assert "--mount=type=secret,id=alpaca_env,uid=10001,required=false" in dockerfile
    assert "build auto --secrets-file /run/secrets/alpaca_env" in dockerfile
    assert not any(line.startswith(("ARG ALPACA", "ENV ALPACA")) for line in dockerfile.splitlines())
    assert "alpaca.env" in dockerignore


def test_container_starts_through_the_refreshing_entrypoint():
    dockerfile = (ROOT / "proyectos/proyecto_iii/Dockerfile").read_text()
    assert dockerfile.rstrip().endswith('CMD ["python", "-m", "dsia_web.serve"]')
    assert "--start-period=120s" in dockerfile


def test_procfile_starts_uvicorn_without_the_access_log():
    # >> El access log de Uvicorn escribe la IP del par TCP; la línea «request» del middleware ya basta.
    [web] = [line for line in (ROOT / "Procfile").read_text().splitlines() if line.startswith("web:")]
    assert web.rstrip().endswith("exec uvicorn dsia_web.app:app --host 0.0.0.0 --port $PORT --no-access-log")


DOCKER_RUN_RECIPES = ["proyectos/proyecto_iii/Dockerfile", ".github/workflows/ci.yml", "README.md",
                      "proyectos/proyecto_iii/README.md", "README_DSIA.md"]


def test_every_docker_run_recipe_without_a_proxy_ignores_x_forwarded_for():
    # >> Sin proxy delante, el último salto de X-Forwarded-For lo escribe el cliente: con el valor por
    #    defecto (1) bastaría inventarlo para saltarse el límite de uso. Toda receta `docker run -p` fija 0.
    recipes = [(name, line.strip()) for name in DOCKER_RUN_RECIPES
               for line in (ROOT / name).read_text().splitlines() if re.search(r"docker run .*-p \d", line)]
    assert len(recipes) >= 4, recipes
    assert [recipe for recipe in recipes if "-e DSIA_TRUSTED_PROXY_HOPS=0" not in recipe[1]] == []


def test_alpaca_secret_file_is_ignored_by_git_and_kept_out_of_the_image():
    # >> README y Dockerfile piden crear alpaca.env para `docker build --secret`: nunca debe versionarse
    #    ni copiarse en la imagen, esté en la raíz o dentro de un proyecto (03_despliegue A2 y B1).
    dockerignore = (ROOT / ".dockerignore").read_text().split()
    assert {"**/alpaca.env", "**/*.env"} <= set(dockerignore)
    git = shutil.which("git")
    if git is None:
        pytest.skip("git no está disponible")
    paths = ["alpaca.env", "proyectos/proyecto_iii/alpaca.env", "proyectos/proyecto_ii/otra-clave.env"]
    result = subprocess.run([git, "check-ignore", "--no-index", *paths], cwd=ROOT, capture_output=True, text=True)
    if result.returncode == 128:
        pytest.skip("no es un repositorio git")
    assert result.stdout.split() == paths
    kept = subprocess.run([git, "check-ignore", "--no-index", "proyectos/proyecto_iii/.env.example"], cwd=ROOT,
                          capture_output=True, text=True)
    assert kept.returncode == 1  # > La plantilla sí se versiona.


def test_react_flow_vendor_ships_without_npm_in_the_image():
    # > El lienzo de React Flow se sirve desde dsia_web/static/vendor, que el Dockerfile ya copia con el III:
    #   ni node_modules ni el directorio frontend (package.json, lockfile y vendor.mjs) entran en la imagen.
    dockerignore = (ROOT / ".dockerignore").read_text().split()
    assert {"**/node_modules", "proyectos/proyecto_iii/frontend"} <= set(dockerignore)
    assert "**/node_modules" in (ROOT / ".gitignore").read_text().split()
    dockerfile = (ROOT / "proyectos/proyecto_iii/Dockerfile").read_text()
    assert "COPY proyectos/proyecto_iii proyectos/proyecto_iii" in dockerfile
    assert "npm" not in dockerfile and "node" not in dockerfile.lower().replace("nodes", "")
