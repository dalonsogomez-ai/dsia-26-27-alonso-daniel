"""-> Workbench marimo: inspección, EDA y contrato (sin entrenar modelos)."""
import marimo

__generated_with = '0.25.2'
app = marimo.App(width='medium')


@app.cell
def _():
    import marimo as mo
    from os import getenv
    from pathlib import Path
    from swarmtrade_app.inspection import inspect_dataset
    return Path, getenv, inspect_dataset, mo


@app.cell
def _(Path, getenv, inspect_dataset):
    data_path = Path(getenv('DSIA_DATA_PATH', 'data/demo.csv'))
    output_dir = Path(getenv('DSIA_EDA_DIR', 'runs/demo-inspection'))
    summary = inspect_dataset(data_path, output_dir)
    return output_dir, summary,


@app.cell
def _(mo, summary):
    mo.md(f'''# SwarmTrader × DSIA — inspección

    {summary['raw_rows']:,} barras, {summary['symbols']} símbolos, {summary['dates']} fechas.
    Ventana: {summary['start']} → {summary['end']}.
    Claves duplicadas: {summary['duplicate_keys']}.

    Contrato propuesto: retorno close[t+21]/close[t]−1, en unidades decimales,
    por fecha/símbolo. Features conocidas al cierre; split temporal con purga de 21 sesiones.
    RMSE principal y MAE secundaria, frente a Dummy y Ridge.
    La explicación HF se ejecuta después de inferir y no altera el score.
    ''')
    return


@app.cell
def _(mo, output_dir):
    mo.vstack([mo.image(str(output_dir / 'figures' / name)) for name in
               ['01_missingness.png', '02_target_balance.png', '02_distributions.png',
                '02_correlations.png', '02_temporal_coverage.png']])
    return


if __name__ == '__main__':
    app.run()
