import json
import shutil

import pytest
from swarmtrade_app.ai_client import AIClient, AIClientError
from swarmtrade_app.data import DataError

from dsia_web.ai import client_from_env
from dsia_web.build import from_run, main
from dsia_web.snapshot import read_snapshot


def test_client_from_env_reads_the_same_variables_as_the_cli_of_project_ii():
    client = client_from_env(env={"AI_PROVIDER": "hf", "HF_MODEL": "org/modelo", "HF_TIMEOUT": "12.5",
                                  "HF_MAX_TOKENS": "100", "HF_INFERENCE_PROVIDER": "together"})
    assert (client.provider, client.model, client.timeout, client.max_tokens, client.inference_provider) == (
        "hf", "org/modelo", 12.5, 100, "together")


def test_client_from_env_reads_nvidia_variables():
    client = client_from_env("nvidia", env={"NVIDIA_MODEL": "nvidia/nemotron-3-ultra-550b-a55b",
                                            "NVIDIA_TIMEOUT": "45", "NVIDIA_MAX_TOKENS": "2048"})
    assert (client.provider, client.model, client.timeout, client.max_tokens) == (
        "nvidia", "nvidia/nemotron-3-ultra-550b-a55b", 45.0, 2048)
    with pytest.raises(AIClientError, match="NVIDIA_MODEL debe tener el formato propietario/nombre"):
        client_from_env("nvidia", env={"NVIDIA_MODEL": "kimi"})


def test_from_run_with_nvidia_publishes_explanation_with_provider_nvidia(demo_run, monkeypatch):
    # >> El contrato del snapshot acepta la explicación de NVIDIA (Explanation.provider).
    from swarmtrade_app.ai_client import AIResponse

    # > Sin el NVIDIA_MODEL local, el modelo esperado es el de por defecto (igual que en test_analyze.py).
    monkeypatch.delenv("NVIDIA_MODEL", raising=False)
    monkeypatch.setattr(AIClient, "analyze", lambda self, request: AIResponse(
        self.provider, "chat_completion", self.model, "Explicación NVIDIA"))
    snapshot = from_run(demo_run.bars, demo_run.run, "nvidia")
    assert (snapshot.explanation.provider, snapshot.explanation.model) == ("nvidia", "moonshotai/kimi-k3.1-pro")


def test_build_cli_accepts_provider_nvidia(demo_run, tmp_path, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    output = tmp_path / "snapshot.json"
    assert main(["from-run", "--data", str(demo_run.bars), "--run", str(demo_run.run),
                 "--output", str(output), "--provider", "nvidia"]) == 0
    # nvidia sin clave -> AIClientError -> el informe se publica sin explicación
    assert read_snapshot(output).explanation is None


def test_client_from_env_defaults_to_mock_and_explicit_provider_wins():
    client = client_from_env(env={})
    assert (client.provider, client.model, client.timeout, client.max_tokens, client.inference_provider) == (
        "mock", "Qwen/Qwen2.5-7B-Instruct", 30.0, 256, "auto")
    assert client_from_env("mock", env={"AI_PROVIDER": "hf"}).provider == "mock"


@pytest.mark.parametrize("env", [{"HF_TIMEOUT": "rápido"}, {"HF_MAX_TOKENS": "1.5"},
                                 {"HF_TIMEOUT": "500"}, {"AI_PROVIDER": "openai"}])
def test_client_from_env_rejects_invalid_configuration_with_typed_error(env):
    with pytest.raises(AIClientError):
        client_from_env(env=env)


@pytest.mark.parametrize(("env", "message"), [
    ({"HF_TIMEOUT": "rápido"}, "HF_TIMEOUT debe ser un número entre 1 y 120"),
    ({"HF_MAX_TOKENS": "0"}, "HF_MAX_TOKENS debe ser un número entre 1 y 512"),
    ({"HF_MODEL": "modelo-sin-propietario"}, "HF_MODEL debe tener el formato propietario/nombre"),
    ({"HF_INFERENCE_PROVIDER": "Together AI"}, "HF_INFERENCE_PROVIDER debe ser auto o un identificador")])
def test_client_from_env_uses_the_domain_messages_of_project_ii_factory(env, message):
    with pytest.raises(AIClientError, match=message):
        client_from_env(env=env)


def test_client_from_env_delegates_to_ai_client_from_env(monkeypatch):
    seen = {}

    def fake_from_env(environ=None):
        seen["environ"] = dict(environ)
        return "cliente"

    monkeypatch.setattr(AIClient, "from_env", staticmethod(fake_from_env))
    assert client_from_env("huggingface", env={"AI_PROVIDER": "mock", "HF_MODEL": "org/m"}) == "cliente"
    assert seen["environ"] == {"AI_PROVIDER": "huggingface", "HF_MODEL": "org/m"}


def test_from_run_provider_defaults_to_ai_provider(demo_run, tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "hf")
    monkeypatch.setenv("HF_TOKEN", "")
    output = tmp_path / "snapshot.json"
    assert main(["from-run", "--data", str(demo_run.bars), "--run", str(demo_run.run),
                 "--output", str(output)]) == 0
    # hf sin token -> AIClientError -> el informe se publica sin explicación
    assert read_snapshot(output).explanation is None


def test_ai_failure_in_batch_publishes_snapshot_without_explanation(demo_run, monkeypatch):
    def failing(self, request):
        raise AIClientError("proveedor caído")

    monkeypatch.setattr(AIClient, "analyze", failing)
    snapshot = from_run(demo_run.bars, demo_run.run)
    assert snapshot.explanation is None
    assert [row.model_dump() for row in snapshot.predictions] == [
        row.model_dump() for row in demo_run.snapshot.predictions]
    assert json.loads(snapshot.model_dump_json())["explanation"] is None


def test_from_run_journal_validates_input_before_inference(demo_run, tmp_path):
    output, journal = tmp_path / "snapshot.json", tmp_path / "pipeline.jsonl"
    assert main(["from-run", "--data", str(demo_run.bars), "--run", str(demo_run.run),
                 "--output", str(output), "--journal", str(journal)]) == 0
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [(event["stage"], event["status"]) for event in events] == [
        (stage, status) for stage in ("validate_input", "infer_snapshot", "publish_snapshot")
        for status in ("started", "succeeded")]
    validated = events[1]
    snapshot = read_snapshot(output)
    assert (validated["rows"], validated["symbols"], validated["input_sha256"]) == (
        680 * 8, 8, snapshot.input_sha256)
    assert "rows" not in events[0]
    assert str(demo_run.bars) not in journal.read_text()


def test_invalid_input_fails_in_validate_input_and_publishes_nothing(demo_run, tmp_path):
    broken = tmp_path / "bars.csv"
    broken.write_text("date,symbol,close\n2026-01-02,AAA,1\n")
    output, journal = tmp_path / "snapshot.json", tmp_path / "pipeline.jsonl"
    assert main(["from-run", "--data", str(broken), "--run", str(demo_run.run),
                 "--output", str(output), "--journal", str(journal)]) == 2
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [(event["stage"], event["status"], event.get("error_type")) for event in events] == [
        ("validate_input", "started", None), ("validate_input", "failed", "DataError")]
    assert not output.exists()


@pytest.mark.parametrize("change", [{"touches": 2}, {"selected": "dummy"}])
def test_from_run_rejects_holdout_not_matching_the_frozen_model(demo_run, tmp_path, change):
    run = tmp_path / "run"
    shutil.copytree(demo_run.run, run)
    metrics = json.loads((run / "test_metrics.json").read_text())
    metrics.update(change)
    (run / "test_metrics.json").write_text(json.dumps(metrics))
    output = tmp_path / "snapshot.json"
    with pytest.raises(DataError, match="holdout"):
        from_run(demo_run.bars, run)
    assert main(["from-run", "--data", str(demo_run.bars), "--run", str(run),
                 "--output", str(output)]) == 2
    assert not output.exists()


def test_from_run_rejects_input_different_from_the_evaluated_dataset(demo_run, tmp_path):
    header, *rows = demo_run.bars.read_text().splitlines()
    reordered = tmp_path / "bars.csv"
    # Mismas barras en otro orden: el contrato las acepta pero el hash ya no es el evaluado.
    reordered.write_text("\n".join([header, *reversed(rows)]) + "\n")
    output = tmp_path / "snapshot.json"
    with pytest.raises(DataError, match="no coincide"):
        from_run(reordered, demo_run.run)
    assert main(["from-run", "--data", str(reordered), "--run", str(demo_run.run),
                 "--output", str(output)]) == 2
    assert not output.exists()


def test_existing_output_is_rejected_before_any_work(demo_run, tmp_path):
    output = tmp_path / "snapshot.json"
    output.write_text("anterior")
    journal = tmp_path / "pipeline.jsonl"
    assert main(["from-run", "--data", str(demo_run.bars), "--run", str(demo_run.run),
                 "--output", str(output), "--journal", str(journal)]) == 2
    assert output.read_text() == "anterior"
    assert not journal.exists()
