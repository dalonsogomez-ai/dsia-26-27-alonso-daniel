""">> El runtime de la imagen usa exactamente las versiones fijadas del II."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", re.MULTILINE)


def pins(path: Path) -> dict[str, str]:
    return {name.lower().replace("_", "-"): version for name, version in PIN.findall(path.read_text())}


def test_runtime_requirements_are_a_subset_of_project_ii_pins():
    runtime = pins(ROOT / "proyectos/proyecto_iii/requirements-runtime.txt")
    shared = pins(ROOT / "proyectos/proyecto_ii/requirements.txt")
    # Arrange/Act: dependencias que el lote demo, la API y el cliente de IA necesitan en la imagen.
    for needed in ("scikit-learn", "starlette", "uvicorn", "pydantic", "huggingface-hub", "pandas"):
        assert needed in runtime, needed
    # Assert: ninguna versión nueva ni distinta respecto al entorno probado del II y el III.
    assert {name: version for name, version in runtime.items() if shared.get(name) != version} == {}
    assert not {"marimo", "pytest", "pytest-cov", "alpaca-py"} & runtime.keys()


def test_dockerfile_installs_the_runtime_requirements():
    dockerfile = (ROOT / "proyectos/proyecto_iii/Dockerfile").read_text()
    assert "pip install --no-cache-dir -r proyectos/proyecto_iii/requirements-runtime.txt" in dockerfile
