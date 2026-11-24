"""-> Interfaz reproducible del Proyecto II; lógica reutilizable fuera de la CLI."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from ml_pipeline import guard

from .ai_client import (DEFAULT_HF_MODEL, DEFAULT_NVIDIA_MODEL, AIClient, AIClientError, AnalysisRequest,
                        provider_name)
from .data import DataError, generate_demo
from .paper import PaperError

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger(__name__)
PROVIDERS = ['mock', 'hf', 'nvidia']
PROVIDER_HELP = 'mock, hf (o su alias huggingface) o nvidia; por defecto AI_PROVIDER o mock'
MODEL_HELP = (f'propietario/nombre; por defecto HF_MODEL o {DEFAULT_HF_MODEL} con hf, '
              f'NVIDIA_MODEL o {DEFAULT_NVIDIA_MODEL} con nvidia')
SECRET_ENV = {'hf': 'HF_TOKEN', 'nvidia': 'NVIDIA_API_KEY'}


def client_from_args(args: argparse.Namespace) -> AIClient:
    """> --provider y --model sustituyen a AI_PROVIDER y al modelo del proveedor (HF_MODEL o NVIDIA_MODEL)."""
    provider = args.provider or provider_name(os.environ.get('AI_PROVIDER') or 'mock')
    model_env = 'NVIDIA_MODEL' if provider == 'nvidia' else 'HF_MODEL'
    overrides = {name: value for name, value in (('AI_PROVIDER', args.provider), (model_env, args.model)) if value}
    return AIClient.from_env({**os.environ, **overrides})


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / '.env', override=False)
    parser = argparse.ArgumentParser(prog='python -m swarmtrade_app',
                                     description='-> SwarmTrader × DSIA: datos, sklearn y API HF o NVIDIA')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Nivel de los logs por etapa en stderr (antes del subcomando)')
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect', help='Perfil y EDA sin entrenar modelos')
    inspect.add_argument('--data', type=Path, required=True)
    inspect.add_argument('--output', type=Path, required=True,
                         help='Directorio fuera del código, p. ej. runs/demo-inspection')
    demo = commands.add_parser('demo-data', help='CSV sintético reproducible, libre de datos Alpaca')
    demo.add_argument('--output', type=Path, required=True)
    demo.add_argument('--sessions', type=int, default=900)
    demo.add_argument('--symbols', type=int, default=8)
    demo.add_argument('--seed', type=int, default=42)
    train = commands.add_parser('train', help='Preparar, comparar sklearn y persistir el ganador')
    train.add_argument('--data', type=Path)
    train.add_argument('--run', type=Path, required=True)
    train.add_argument('--prepared', action='store_true', help='Continuar una preparación existente sin recrear el split')
    train.add_argument('--data-kind', choices=['synthetic', 'alpaca', 'local'], default='local')
    train.add_argument('--ledger', type=Path)
    evaluate = commands.add_parser('evaluate', help='Evaluación única del holdout congelado')
    evaluate.add_argument('--run', type=Path, required=True)
    evaluate.add_argument('--ledger', type=Path)
    run = commands.add_parser('run', help='Cargar modelo, inferir, asignar y explicar con HF, NVIDIA o mock')
    run.add_argument('--data', type=Path, required=True)
    run.add_argument('--artifact', type=Path, required=True)
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--decision', choices=['conviction', 'research'], default='conviction')
    run.add_argument('--risk-aversion', type=float, default=1)
    run.add_argument('--scenarios', type=int, default=3000)
    run.add_argument('--mean-source', choices=['model', 'empirical'], default='model')
    run.add_argument('--provider', type=provider_name, choices=PROVIDERS, help=PROVIDER_HELP)
    run.add_argument('--model', help=MODEL_HELP)
    plan = commands.add_parser('paper-plan', help='Consultar cuenta paper y guardar plan; no envía órdenes')
    plan.add_argument('--report', type=Path, required=True)
    plan.add_argument('--output', type=Path, required=True)
    plan.add_argument('--buffer-bps', type=float, default=0)
    execute = commands.add_parser('paper-execute', help='Enviar el plan explícitamente a Alpaca PAPER')
    execute.add_argument('--plan', type=Path, required=True)
    execute.add_argument('--journal', type=Path, required=True)
    execute.add_argument('--liquidate', action='store_true', help='Liquidar posiciones previas y esperar su cierre')
    analyze = commands.add_parser('analyze-summary', help='Explicar un resumen agregado tipado')
    analyze.add_argument('--summary', type=Path, required=True)
    analyze.add_argument('--provider', type=provider_name, choices=PROVIDERS, help=PROVIDER_HELP)
    analyze.add_argument('--model', help=MODEL_HELP)
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    logging.getLogger().setLevel(args.log_level)
    # > matplotlib publica avisos de unidades categóricas a INFO que no aportan a la traza del pipeline.
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    try:
        LOG.info('Inicio command=%s', args.command)
        if args.command == 'inspect':
            from .inspection import inspect_dataset
            result = inspect_dataset(args.data, args.output)
        elif args.command == 'demo-data':
            result = {'csv': str(generate_demo(args.output, args.sessions, args.symbols, args.seed)),
                      'data_kind': 'synthetic', 'seed': args.seed}
        elif args.command == 'train':
            from .preparation import prepare
            from .training import train_prepared
            if not args.prepared:
                if args.data is None:
                    raise DataError('--data es obligatorio salvo con --prepared')
                prepare(args.data, args.run, data_kind=args.data_kind, ledger=args.ledger)
            result = train_prepared(args.run, ledger=args.ledger)
        elif args.command == 'evaluate':
            from .training import evaluate_holdout
            result = evaluate_holdout(args.run, ledger=args.ledger)
        elif args.command.startswith('paper-'):
            from .paper import PaperBroker
            broker = PaperBroker()
            if args.command == 'paper-plan':
                if args.output.exists():
                    raise PaperError('El plan de salida ya existe')
                result = broker.plan(json.loads(args.report.read_text()), buffer_bps=args.buffer_bps)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2))
            else:
                result = broker.execute(json.loads(args.plan.read_text()), args.journal, liquidate=args.liquidate)
        else:
            from .pipeline import run_pipeline
            client = client_from_args(args)
            secret = SECRET_ENV.get(client.provider)
            if secret and not os.getenv(secret, '').strip():
                # > Error de configuración: se detecta antes de inferir/optimizar. El informe `pending`
                # queda para fallos del servicio HF o NVIDIA una vez iniciada la llamada.
                raise AIClientError(f'Falta {secret} en el entorno')
            if args.command == 'run':
                result = run_pipeline(args.data, args.artifact, args.output, client, decision=args.decision,
                                      risk_aversion=args.risk_aversion, scenarios=args.scenarios,
                                      mean_source=args.mean_source)
            else:
                request = AnalysisRequest.from_dict(json.loads(args.summary.read_text()))
                result = asdict(client.analyze(request))
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False, allow_nan=False))
        LOG.info('Fin command=%s', args.command)
        return 0
    except guard.TestSetAlreadyUsed:
        # > El mensaje del guard vendorizado está pensado para un agente; aquí se traduce al usuario.
        LOG.error('El holdout de este run ya se evaluó una vez; entrena un run nuevo para volver a evaluar')
        return 2
    except (AIClientError, PaperError, DataError, ValueError, OSError, TypeError, KeyError, RuntimeError) as exc:
        # > Las excepciones externas del SDK se redactan en el borde AIClient.
        LOG.error('%s', str(exc))
        return 2
