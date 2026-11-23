import json

import pytest
from swarmtrade_app.ai_client import AIClient, AIClientError

from dsia_web.ai import client_from_env
from dsia_web.build import from_run, main
from dsia_web.snapshot import read_snapshot


def test_client_from_env_reads_the_same_variables_as_the_cli_of_project_ii():
    client = client_from_env(env={"AI_PROVIDER": "hf", "HF_MODEL": "org/modelo", "HF_TIMEOUT": "12.5",
                                  "HF_MAX_TOKENS": "100", "HF_INFERENCE_PROVIDER": "together"})
    assert (client.provider, client.model, client.timeout, client.max_tokens, client.inference_provider) == (
        "hf", "org/modelo", 12.5, 100, "together")


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
