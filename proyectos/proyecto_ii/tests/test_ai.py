from types import SimpleNamespace

import pytest

from swarmtrade_app.ai_client import AIClient, AIClientError, AnalysisRequest
from swarmtrade_app.cli import main


@pytest.fixture
def request_data():
    return AnalysisRequest('2026-09-28', 'swarm_ridge', 21, 10, 0.012, 0.09, 'synthetic')


def test_mock_never_needs_secret(request_data, monkeypatch):
    monkeypatch.delenv('HF_TOKEN', raising=False)
    a = AIClient('mock').analyze(request_data)
    assert a == AIClient('mock').analyze(request_data)
    assert a.provider == 'mock' and a.task == 'chat_completion'


def test_real_client_missing_token(request_data, monkeypatch):
    monkeypatch.delenv('HF_TOKEN', raising=False)
    with pytest.raises(AIClientError, match='HF_TOKEN'):
        AIClient('hf').analyze(request_data)


def test_sdk_contract_without_network(request_data, monkeypatch):
    import huggingface_hub
    calls = {}
    class FakeClient:
        def __init__(self, **kwargs):
            calls['config'] = kwargs
        def chat_completion(self, **kwargs):
            calls['request'] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Resumen técnico'))])
    monkeypatch.setenv('HF_TOKEN', 'test-token-not-a-real-credential')
    monkeypatch.setattr(huggingface_hub, 'InferenceClient', FakeClient)
    result = AIClient('hf').analyze(request_data)
    assert result.text == 'Resumen técnico'
    assert calls['request']['max_tokens'] == 256
    assert calls['config']['timeout'] == 30
    assert 'symbol' not in calls['request']['messages'][-1]['content'].replace('n_symbols', '')


def test_provider_failure_is_redacted(request_data, monkeypatch):
    import huggingface_hub
    class BadClient:
        def __init__(self, **kwargs):
            raise RuntimeError('a-secret-in-response')
    monkeypatch.setenv('HF_TOKEN', 'a-secret-in-response')
    monkeypatch.setattr(huggingface_hub, 'InferenceClient', BadClient)
    with pytest.raises(AIClientError) as err:
        AIClient('hf').analyze(request_data)
    assert 'a-secret-in-response' not in str(err.value)


@pytest.mark.parametrize('kwargs', [{'provider': 'unknown'}, {'timeout': 0}, {'max_tokens': 1000}])
def test_invalid_client_config(kwargs):
    with pytest.raises(AIClientError):
        AIClient(**kwargs)


@pytest.mark.integration
def test_cli_demo_data(tmp_path, capsys):
    output = tmp_path / 'bars.csv'
    assert main(['demo-data', '--output', str(output), '--sessions', '450', '--symbols', '5']) == 0
    assert output.exists() and 'synthetic' in capsys.readouterr().out


def test_cli_reports_data_failure(tmp_path):
    assert main(['demo-data', '--output', str(tmp_path / 'x.csv'), '--sessions', '4']) == 2
