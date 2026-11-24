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


def test_kwargs_match_real_inference_client_signature(request_data, monkeypatch):
    # >> FakeClient(**kwargs) aceptaría cualquier argumento; se contrastan con la clase real del SDK.
    import inspect
    import huggingface_hub
    real = huggingface_hub.InferenceClient
    calls = {}
    class Recorder:
        def __init__(self, **kwargs):
            calls['config'] = kwargs
        def chat_completion(self, **kwargs):
            calls['request'] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='ok'))])
    monkeypatch.setenv('HF_TOKEN', 'test-token-not-a-real-credential')
    monkeypatch.setattr(huggingface_hub, 'InferenceClient', Recorder)
    AIClient('hf').analyze(request_data)
    inspect.signature(real.__init__).bind(None, **calls['config'])
    inspect.signature(real.chat_completion).bind(None, **calls['request'])
    assert calls['config']['provider'] == 'auto'


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


@pytest.mark.parametrize('alias', ['huggingface', ' HF ', 'HuggingFace'])
def test_huggingface_alias_is_normalized(alias):
    from swarmtrade_app.cli import provider_name
    assert AIClient(alias).provider == 'hf'
    assert provider_name(alias) == 'hf'
    assert provider_name(' Mock ') == 'mock'


@pytest.mark.parametrize('name,value,message', [
    ('HF_TIMEOUT', 'abc', 'HF_TIMEOUT debe ser un número entre 1 y 120'),
    ('HF_TIMEOUT', '0', 'HF_TIMEOUT debe ser un número entre 1 y 120'),
    ('HF_TIMEOUT', 'nan', 'HF_TIMEOUT debe ser un número entre 1 y 120'),
    ('HF_MAX_TOKENS', '12.5', 'HF_MAX_TOKENS debe ser un número entre 1 y 512'),
    ('HF_MAX_TOKENS', '9999', 'HF_MAX_TOKENS debe ser un número entre 1 y 512')])
def test_env_limits_have_domain_errors(monkeypatch, name, value, message):
    from swarmtrade_app.cli import env_number
    from swarmtrade_app.data import DataError
    monkeypatch.setenv(name, value)
    high, cast = (120, float) if name == 'HF_TIMEOUT' else (512, int)
    with pytest.raises(DataError, match=message):
        env_number(name, '30', cast, 1, high)


def test_env_limits_defaults_and_valid_values(monkeypatch):
    from swarmtrade_app.cli import env_number
    assert env_number('HF_TIMEOUT', '30', float, 1, 120) == 30.0
    monkeypatch.setenv('HF_MAX_TOKENS', ' 128 ')
    assert env_number('HF_MAX_TOKENS', '256', int, 1, 512) == 128


# --- A6: la suite no alcanza la red por ninguna vía -----------------------------------------------

def test_suite_blocks_dns_and_connect_ex():
    import socket
    with pytest.raises(AssertionError, match='sin red'):
        socket.getaddrinfo('huggingface.co', 443)
    probe = socket.socket()
    try:
        with pytest.raises(AssertionError, match='sin red'):
            probe.connect_ex(('127.0.0.1', 9))
    finally:
        probe.close()


def test_subprocess_environment_is_mock_without_hf_variables(monkeypatch, offline_env):
    import os
    monkeypatch.setenv('AI_PROVIDER', 'hf')
    monkeypatch.setenv('HF_TOKEN', 'hf_no-debe-viajar')
    monkeypatch.setenv('HF_INFERENCE_PROVIDER', 'together')
    env = offline_env()
    assert env['AI_PROVIDER'] == 'mock'
    assert not [name for name in env if name.startswith('HF_')]
    assert env['PATH'] == os.environ['PATH']


def test_cli_reports_invalid_timeout_clearly(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv('HF_TIMEOUT', 'abc')
    summary = tmp_path / 'summary.json'
    summary.write_text('{}')
    assert main(['analyze-summary', '--summary', str(summary)]) == 2
    assert 'HF_TIMEOUT debe ser un número entre 1 y 120' in caplog.text


def test_cli_checks_token_before_heavy_work(tmp_path, caplog):
    # >> Sin HF_TOKEN no se carga el CSV ni el artefacto: los paths ni siquiera existen.
    output = tmp_path / 'hf.json'
    assert main(['run', '--data', str(tmp_path / 'missing.csv'), '--artifact', str(tmp_path / 'missing.joblib'),
                 '--output', str(output), '--provider', 'huggingface']) == 2
    assert 'Falta HF_TOKEN' in caplog.text
    assert not output.exists()


@pytest.mark.integration
def test_cli_demo_data(tmp_path, capsys):
    output = tmp_path / 'bars.csv'
    assert main(['demo-data', '--output', str(output), '--sessions', '450', '--symbols', '5']) == 0
    assert output.exists() and 'synthetic' in capsys.readouterr().out


def test_cli_reports_data_failure(tmp_path):
    assert main(['demo-data', '--output', str(tmp_path / 'x.csv'), '--sessions', '4']) == 2
