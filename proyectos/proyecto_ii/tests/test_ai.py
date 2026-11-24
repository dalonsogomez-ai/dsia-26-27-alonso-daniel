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
        AIClient('hf', sleep=lambda seconds: None).analyze(request_data)
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
    ('HF_MAX_TOKENS', '9999', 'HF_MAX_TOKENS debe ser un número entre 1 y 512'),
    ('HF_MODEL', 'sin-propietario', 'HF_MODEL debe tener el formato propietario/nombre'),
    ('HF_MODEL', 'a/b/c', 'HF_MODEL debe tener el formato propietario/nombre'),
    ('HF_INFERENCE_PROVIDER', 'Together', 'HF_INFERENCE_PROVIDER debe ser auto o un identificador'),
    ('HF_INFERENCE_PROVIDER', 'fal ai', 'HF_INFERENCE_PROVIDER debe ser auto o un identificador'),
    ('AI_PROVIDER', 'openai', 'Proveedor no soportado')])
def test_from_env_rejects_invalid_values_with_domain_errors(name, value, message):
    with pytest.raises(AIClientError, match=message):
        AIClient.from_env({name: value})


def test_from_env_defaults_and_valid_values():
    from swarmtrade_app.ai_client import DEFAULT_HF_MODEL
    default = AIClient.from_env({})
    assert DEFAULT_HF_MODEL == 'Qwen/Qwen2.5-7B-Instruct'
    assert (default.provider, default.model, default.timeout, default.max_tokens, default.inference_provider) == (
        'mock', DEFAULT_HF_MODEL, 30.0, 256, 'auto')
    custom = AIClient.from_env({'AI_PROVIDER': ' HuggingFace ', 'HF_MODEL': 'meta-llama/Llama-3.1-8B-Instruct',
                                'HF_TIMEOUT': '12.5', 'HF_MAX_TOKENS': ' 128 ',
                                'HF_INFERENCE_PROVIDER': 'fireworks-ai'})
    assert (custom.provider, custom.model, custom.timeout, custom.max_tokens, custom.inference_provider) == (
        'hf', 'meta-llama/Llama-3.1-8B-Instruct', 12.5, 128, 'fireworks-ai')
    # > Variables vacías o con espacios equivalen a no definidas.
    assert AIClient.from_env({'AI_PROVIDER': ' ', 'HF_TIMEOUT': ''}).timeout == 30.0


def test_from_env_reads_process_environment_by_default(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER', 'hf')
    monkeypatch.setenv('HF_MAX_TOKENS', '64')
    client = AIClient.from_env()
    assert (client.provider, client.max_tokens) == ('hf', 64)


# --- A1: resumen para la IA con dispersión, spread y mejor señal ---------------------------------

def test_new_summary_fields_are_optional_for_old_reports(request_data):
    assert (request_data.prediction_std, request_data.prediction_spread, request_data.top_symbol) == (None, None, None)


@pytest.mark.parametrize('changes,reason', [
    ({'as_of': '28/09/2026'}, 'as_of'), ({'as_of': 20260928}, 'as_of'),
    ({'model': ''}, 'model'), ({'horizon': 0}, 'horizon'), ({'horizon': 2.5}, 'horizon'),
    ({'horizon': True}, 'horizon'), ({'symbols': -1}, 'symbols'),
    ({'mean_prediction': float('nan')}, 'mean_prediction'), ({'mean_prediction': '0.01'}, 'mean_prediction'),
    ({'validation_rmse': -0.1}, 'validation_rmse'), ({'validation_rmse': float('inf')}, 'validation_rmse'),
    ({'prediction_std': float('nan')}, 'prediction_std'), ({'prediction_std': -0.01}, 'prediction_std'),
    ({'prediction_spread': float('inf')}, 'prediction_spread'), ({'prediction_spread': -1.0}, 'prediction_spread'),
    ({'top_symbol': ''}, 'top_symbol'), ({'top_symbol': 3}, 'top_symbol'),
    ({'data_kind': 'real'}, 'data_kind')])
def test_summary_validates_types_and_ranges(request_data, changes, reason):
    import dataclasses
    with pytest.raises(AIClientError, match=f'Resumen para la IA no válido: {reason}'):
        dataclasses.replace(request_data, **changes)


def test_mock_mentions_dispersion_and_top_signal():
    request = AnalysisRequest('2026-09-28', 'ridge', 21, 8, 0.0012, 0.064383, 'synthetic',
                              prediction_std=0.0123, prediction_spread=0.04, top_symbol='DEMO03')
    assert AIClient('mock').analyze(request).text == (
        '[mock] Modelo ridge; horizonte 21 sesiones; 8 símbolos; media predicha 0.1200%; '
        'dispersión entre símbolos 1.2300%; rango de predicciones 4.0000%; mejor señal DEMO03; '
        'RMSE validación 0.064383. La predicción no demuestra rentabilidad ni incluye costes de ejecución.')


def test_mock_text_without_new_fields_is_unchanged(request_data):
    assert AIClient('mock').analyze(request_data).text == (
        '[mock] Modelo swarm_ridge; horizonte 21 sesiones; 10 símbolos; media predicha 1.2000%; '
        'RMSE validación 0.090000. La predicción no demuestra rentabilidad ni incluye costes de ejecución.')


def test_hf_payload_carries_dispersion_spread_and_top_signal(monkeypatch):
    import json
    import huggingface_hub
    calls = {}
    class Recorder:
        def __init__(self, **kwargs):
            pass
        def chat_completion(self, **kwargs):
            calls['request'] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='ok'))])
    monkeypatch.setenv('HF_TOKEN', 'test-token-not-a-real-credential')
    monkeypatch.setattr(huggingface_hub, 'InferenceClient', Recorder)
    AIClient('hf').analyze(AnalysisRequest('2026-09-28', 'ridge', 21, 8, 0.0012, 0.06, 'synthetic',
                                           prediction_std=0.01, prediction_spread=0.03, top_symbol='DEMO03'))
    payload = json.loads(calls['request']['messages'][-1]['content'])
    assert (payload['prediction_std'], payload['prediction_spread'], payload['top_symbol']) == (0.01, 0.03, 'DEMO03')
    assert 'orden relativo' in calls['request']['messages'][0]['content']


# --- A2: errores del proveedor HF clasificados ---------------------------------------------------

def hf_status_error(status: int):
    """> Error real del SDK con la respuesta httpx que produce InferenceClient (sin red)."""
    import httpx
    from huggingface_hub.errors import HfHubHTTPError
    request = httpx.Request('POST', 'https://router.huggingface.co/v1/chat/completions')
    return HfHubHTTPError(f'{status} Client Error', response=httpx.Response(status, request=request))


def failing_sdk(monkeypatch, errors):
    """> Sustituye InferenceClient por un doble que lanza la secuencia `errors` y después responde."""
    import huggingface_hub
    calls = {'n': 0}
    class Flaky:
        def __init__(self, **kwargs):
            pass
        def chat_completion(self, **kwargs):
            calls['n'] += 1
            if calls['n'] <= len(errors):
                raise errors[calls['n'] - 1]
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='recuperado'))])
    monkeypatch.setenv('HF_TOKEN', 'hf_token-secreto-de-prueba')
    monkeypatch.setattr(huggingface_hub, 'InferenceClient', Flaky)
    return calls


@pytest.mark.parametrize('status,message', [(401, 'Token de Hugging Face inválido o sin permisos'),
                                            (403, 'Token de Hugging Face inválido o sin permisos'),
                                            (404, 'Modelo o proveedor de inferencia no disponible')])
def test_auth_and_not_found_errors_are_not_retried(request_data, monkeypatch, caplog, status, message):
    calls = failing_sdk(monkeypatch, [hf_status_error(status)] * 3)
    waits = []
    with pytest.raises(AIClientError, match=message):
        AIClient('hf', sleep=waits.append).analyze(request_data)
    assert calls['n'] == 1 and waits == []
    assert f'status={status}' in caplog.text
    assert 'hf_token-secreto-de-prueba' not in caplog.text


def transient_errors():
    import httpx
    from huggingface_hub.errors import InferenceTimeoutError
    request = httpx.Request('POST', 'https://router.huggingface.co/v1/chat/completions')
    return [hf_status_error(429), hf_status_error(503), InferenceTimeoutError('timeout'),
            httpx.ConnectError('sin conexión', request=request), httpx.ReadTimeout('lento', request=request)]


@pytest.mark.parametrize('index', range(5))
def test_transient_errors_retry_twice_with_backoff_then_fail(request_data, monkeypatch, index):
    from swarmtrade_app.ai_client import MAX_RETRIES
    error = transient_errors()[index]
    calls = failing_sdk(monkeypatch, [error] * 3)
    waits = []
    with pytest.raises(AIClientError, match='Inferencia HF fallida') as err:
        AIClient('hf', sleep=waits.append).analyze(request_data)
    assert MAX_RETRIES == 2 and calls['n'] == 3
    assert len(waits) == 2
    assert 0.5 <= waits[0] <= 0.6 and 1.0 <= waits[1] <= 1.1
    assert 'hf_token-secreto-de-prueba' not in str(err.value)


def test_transient_error_recovers_on_retry(request_data, monkeypatch, caplog):
    import logging
    caplog.set_level(logging.INFO)
    calls = failing_sdk(monkeypatch, [hf_status_error(502)])
    waits = []
    result = AIClient('hf', sleep=waits.append).analyze(request_data)
    assert result.text == 'recuperado' and calls['n'] == 2 and len(waits) == 1
    assert 'ai_status=completed' in caplog.text and 'attempt=2' in caplog.text


def test_other_client_errors_fail_without_retry(request_data, monkeypatch):
    calls = failing_sdk(monkeypatch, [hf_status_error(400), ValueError('respuesta rara')])
    waits = []
    with pytest.raises(AIClientError, match='Inferencia HF fallida'):
        AIClient('hf', sleep=waits.append).analyze(request_data)
    assert calls['n'] == 1 and waits == []


def test_empty_answer_fails_without_retry(request_data, monkeypatch):
    import huggingface_hub
    calls = {'n': 0}
    class Empty:
        def __init__(self, **kwargs):
            pass
        def chat_completion(self, **kwargs):
            calls['n'] += 1
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='   '))])
    monkeypatch.setenv('HF_TOKEN', 'test-token-not-a-real-credential')
    monkeypatch.setattr(huggingface_hub, 'InferenceClient', Empty)
    waits = []
    with pytest.raises(AIClientError, match='Inferencia HF fallida'):
        AIClient('hf', sleep=waits.append).analyze(request_data)
    assert calls['n'] == 1 and waits == []


# --- A8: CLI ------------------------------------------------------------------------------------

def test_cli_program_name_matches_module_invocation(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(['--help'])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.startswith('usage: python -m swarmtrade_app')


def test_module_entry_point_runs_the_cli(tmp_path, monkeypatch):
    import runpy
    import sys
    output = tmp_path / 'bars.csv'
    monkeypatch.setattr(sys, 'argv', ['swarmtrade_app', 'demo-data', '--output', str(output),
                                      '--sessions', '450', '--symbols', '5'])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module('swarmtrade_app', run_name='__main__')
    assert exit_info.value.code == 0 and output.exists()


@pytest.mark.parametrize('extra,missing,message', [
    ({'question': '¿compro?'}, (), 'claves sobrantes: question'),
    ({}, ('validation_rmse', 'data_kind'), 'faltan claves: data_kind, validation_rmse')])
def test_analyze_summary_reports_bad_keys_as_domain_error(tmp_path, caplog, request_data, extra, missing, message):
    import dataclasses
    import json
    data = {k: v for k, v in dataclasses.asdict(request_data).items() if k not in missing} | extra
    summary = tmp_path / 'summary.json'
    summary.write_text(json.dumps(data))
    assert main(['analyze-summary', '--summary', str(summary)]) == 2
    errors = [r.getMessage() for r in caplog.records if r.levelname == 'ERROR']
    assert errors == [f'Resumen para la IA no válido: {message}']


def test_analyze_summary_requires_a_json_object(tmp_path, caplog):
    summary = tmp_path / 'summary.json'
    summary.write_text('[1, 2]')
    assert main(['analyze-summary', '--summary', str(summary)]) == 2
    assert 'Resumen para la IA no válido: se espera un objeto JSON' in caplog.text


def test_analyze_summary_accepts_full_summary(tmp_path, capsys, request_data):
    import dataclasses
    import json
    summary = tmp_path / 'summary.json'
    summary.write_text(json.dumps(dataclasses.asdict(request_data)))
    assert main(['analyze-summary', '--summary', str(summary), '--provider', 'mock']) == 0
    assert json.loads(capsys.readouterr().out)['provider'] == 'mock'


def test_cli_provider_comes_from_environment(tmp_path, monkeypatch, caplog):
    # >> Sin --provider, AI_PROVIDER=hf llega por AIClient.from_env y se exige HF_TOKEN antes de inferir.
    monkeypatch.setenv('AI_PROVIDER', 'huggingface')
    output = tmp_path / 'hf.json'
    assert main(['run', '--data', str(tmp_path / 'missing.csv'), '--artifact', str(tmp_path / 'm.joblib'),
                 '--output', str(output)]) == 2
    assert 'Falta HF_TOKEN' in caplog.text and not output.exists()


def test_cli_rejects_badly_formed_model_flag(tmp_path, caplog):
    summary = tmp_path / 'summary.json'
    summary.write_text('{}')
    assert main(['analyze-summary', '--summary', str(summary), '--model', 'modelo-sin-propietario']) == 2
    assert 'HF_MODEL debe tener el formato propietario/nombre' in caplog.text


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
