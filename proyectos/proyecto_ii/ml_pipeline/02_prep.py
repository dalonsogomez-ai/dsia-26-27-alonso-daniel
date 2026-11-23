"""-> Workbench de evidencia; no reentrena ni vuelve a tocar el holdout al abrirlo."""
import marimo

__generated_with = '0.25.2'
app = marimo.App(width='medium')


@app.cell
def _():
    import json
    from os import getenv
    from pathlib import Path
    import marimo as mo
    return Path, getenv, json, mo


@app.cell
def _(Path, getenv, json, mo):
    run_path = Path(getenv('DSIA_RUN_DIR', 'runs/demo'))
    evidence = run_path / 'preparation.json'
    mo.md('# Preparación temporal')
    mo.json(json.loads(evidence.read_text()) if evidence.exists() else
            {'estado': 'Ejecuta primero la fase CLI indicada en README.md', 'ruta': str(evidence)})
    return run_path,


@app.cell
def _(mo, run_path):
    figure = run_path / 'figures' / '04_preparation.png'
    mo.image(str(figure)) if figure.is_file() else None
    return


if __name__ == '__main__':
    app.run()
