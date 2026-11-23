"use strict";

const text = (id, value) => { document.getElementById(id).textContent = value; };
const percent = new Intl.NumberFormat("es-ES", {style: "percent", maximumFractionDigits: 2});
const decimal = new Intl.NumberFormat("es-ES", {minimumFractionDigits: 4, maximumFractionDigits: 4});
const millis = new Intl.NumberFormat("es-ES", {minimumFractionDigits: 1, maximumFractionDigits: 1});
const modelNames = {dummy: "Dummy", ridge: "Ridge", swarm: "Swarm sklearn"};
const dataNames = {synthetic: "Simulación sintética", alpaca: "Datos reales · Alpaca", local: "Histórico local"};

function element(tag, content, className) {
  const node = document.createElement(tag);
  if (content !== undefined) node.textContent = content;
  if (className) node.className = className;
  return node;
}

function renderPredictions(predictions) {
  const query = document.getElementById("filter").value.trim().toUpperCase();
  const scale = Math.max(0.001, ...predictions.map(row => Math.abs(row.predicted_return)));
  const matches = predictions.filter(row => row.symbol.toUpperCase().includes(query));
  const rows = matches.map(row => {
    const tr = element("tr");
    const label = element("th", row.symbol);
    label.scope = "row";
    const polarity = row.predicted_return < 0 ? "neg" : "pos";
    const plot = element("td", undefined, "plot");
    plot.setAttribute("aria-hidden", "true");
    const track = element("div", undefined, "track");
    const bar = element("span", undefined, "bar " + polarity);
    const width = 50 * Math.abs(row.predicted_return) / scale;
    bar.style.width = width + "%";
    bar.style.left = (polarity === "neg" ? 50 - width : 50) + "%";
    track.append(bar);
    plot.append(track);
    tr.append(label, element("td", percent.format(row.predicted_return), polarity), plot);
    return tr;
  });
  document.getElementById("predictions").replaceChildren(...rows);
  text("count", matches.length ? `${matches.length} de ${predictions.length} símbolos` : "Ningún símbolo coincide con el filtro.");
}

function render(report) {
  text("status", dataNames[report.data_kind]);
  text("as-of", report.as_of);
  text("model", modelNames[report.model]);
  text("universe", `${report.predictions.length} símbolos`);
  text("rmse", percent.format(report.holdout.rmse));
  text("mae", percent.format(report.holdout.mae));
  text("r2", decimal.format(report.holdout.r2));
  text("touches", report.holdout_touches);
  text("run", report.run_id);
  text("input-hash", report.input_sha256);
  text("artifact-hash", report.artifact_sha256);
  text("sklearn", report.sklearn_version);
  text("generated", new Date(report.generated_at).toLocaleString("es-ES"));
  text("explanation-source", report.explanation
    ? `${report.explanation.provider} · ${report.explanation.model}`
    : "Estado del proveedor");
  text("explanation", report.explanation?.text ?? "Explicación no disponible para este informe.");
  const metrics = Object.entries(report.validation).map(([model, values]) => {
    const row = element("li", undefined, model === report.model ? "selected" : "");
    row.append(element("span", modelNames[model]), element("strong", percent.format(values.rmse)));
    return row;
  });
  document.getElementById("validation").replaceChildren(...metrics);
  const periods = [["train", "Train"], ["validation", "Validation"], ["test", "Holdout"]].map(([key, label]) => {
    const period = report.splits[key];
    const row = element("tr");
    const heading = element("th", label);
    heading.scope = "row";
    row.append(heading, ...[period.start, period.end, period.max_target_end, period.rows]
      .map(value => element("td", value)));
    return row;
  });
  document.getElementById("splits").replaceChildren(...periods);
  const predictions = [...report.predictions].sort((a, b) => b.predicted_return - a.predicted_return);
  renderSpotlight(predictions[0], report.horizon_sessions);
  if (predictions[0]) document.getElementById("filter").placeholder = `p. ej. ${predictions[0].symbol}`;
  text("disclaimer", report.data_kind === "synthetic"
    ? "Investigación académica con datos sintéticos de demostración: no es una recomendación de inversión."
    : "Investigación académica con datos reales: señales de un modelo, no una recomendación de inversión.");
  renderPredictions(predictions);
  document.getElementById("filter").addEventListener("input", () => renderPredictions(predictions));
  renderInputs(report.input_summary, report.data_kind);
  const options = predictions.map(row => {
    const option = element("option", row.symbol);
    option.value = row.symbol;
    return option;
  });
  document.getElementById("analyze-symbol").replaceChildren(...options);
  document.getElementById("results").hidden = false;
}

function renderSpotlight(best, horizon) {
  if (!best) return;
  text("top-symbol", best.symbol);
  const value = document.getElementById("top-return");
  value.textContent = (best.predicted_return > 0 ? "+" : "") + percent.format(best.predicted_return);
  value.classList.toggle("neg", best.predicted_return < 0);
  text("top-note", `Retorno predicho a ${horizon ?? 21} sesiones · señal de investigación, no recomendación`);
}

function renderInputs(summary, dataKind) {
  const price = new Intl.NumberFormat("es-ES", {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const optional = (value, format) => value === null || value === undefined ? "—" : format.format(value);
  const rows = (summary ?? []).map(item => {
    const tr = element("tr");
    const label = element("th", item.symbol);
    label.scope = "row";
    tr.append(label, element("td", String(item.sessions)), element("td", price.format(item.last_close)),
      element("td", optional(item.return_21_sessions, percent)),
      element("td", optional(item.volatility_annualized, percent)));
    return tr;
  });
  const body = document.getElementById("inputs");
  body.replaceChildren(...rows);
  body.closest(".table-wrap").hidden = !rows.length;
  text("inputs-note", rows.length ? `${rows.length} símbolos · fuente: snapshot cargado`
    : dataKind === "alpaca"
      ? "Barras diarias reales de Alpaca, descargadas y reentrenadas en cada despliegue. Sus condiciones no permiten redistribuir los datos, así que el informe público muestra solo las predicciones y las métricas del modelo, sin precios."
      : "Este informe no incluye resumen de datos de entrada.");
}

async function getJSON(url) {
  const response = await fetch(url, {headers: {Accept: "application/json"}});
  let body = null;
  try { body = await response.json(); } catch (error) { body = null; }
  return {ok: response.ok, status: response.status, body};
}

async function renderOperation() {
  const [health, metrics, pipeline] = await Promise.all(
    ["/health", "/api/v1/metrics", "/api/v1/pipeline?limit=12"].map(url => getJSON(url).catch(() => null)));
  const checks = health?.body?.checks ?? {};
  const ready = health?.ok && health.body.status === "ready";
  const status = document.getElementById("ops-status");
  status.textContent = ready ? "Operativo (200)" : `Sin informe válido (${health ? health.status : "sin respuesta"})`;
  status.dataset.state = ready ? "ready" : "unavailable";
  text("ops-run", health?.body?.run_id ?? "—");
  text("ops-as-of", checks.as_of ?? "—");
  text("ops-age", checks.snapshot_age_days === null || checks.snapshot_age_days === undefined
    ? "—" : `${checks.snapshot_age_days} días`);
  if (metrics?.ok) {
    const latency = metrics.body.latency_ms;
    text("ops-requests", String(metrics.body.requests_total));
    text("ops-latency", latency.mean === null ? "—" : `${millis.format(latency.mean)} · ${millis.format(latency.p95)} ms`);
  } else {
    text("ops-requests", "—");
    text("ops-latency", "—");
  }
  const events = pipeline?.ok ? pipeline.body.events : [];
  const rows = events.map(event => {
    const tr = element("tr");
    const stage = element("th", event.stage);
    stage.scope = "row";
    tr.append(stage, element("td", event.status, event.status === "failed" ? "neg" : ""),
      element("td", event.duration_ms === undefined ? "—" : `${millis.format(event.duration_ms)} ms`),
      element("td", event.timestamp ? event.timestamp.slice(11, 19) : "—"));
    return tr;
  });
  document.getElementById("ops-events").replaceChildren(...rows);
  const note = document.getElementById("ops-pipeline-note");
  if (pipeline?.ok) {
    note.textContent = `${pipeline.body.returned} eventos · último run_id publicado: ${pipeline.body.last_run_id ?? "—"}`
      + (pipeline.body.skipped_lines ? ` · ${pipeline.body.skipped_lines} líneas descartadas` : "");
    note.dataset.runId = pipeline.body.last_run_id ?? "";
  } else {
    note.textContent = pipeline?.status === 404 ? "Journal no configurado (DSIA_JOURNAL)." : "Journal no disponible.";
    note.dataset.runId = "";
  }
}

async function analyze(event) {
  event.preventDefault();
  const button = document.getElementById("analyze-submit");
  const result = document.getElementById("analyze-result");
  const failure = document.getElementById("analyze-error");
  const headers = {"Content-Type": "application/json", Accept: "application/json"};
  const key = document.getElementById("analyze-key").value;
  if (key) headers["X-API-Key"] = key;
  button.disabled = true;
  failure.hidden = true;
  try {
    const response = await fetch("/api/v1/analyze", {method: "POST", headers,
      body: JSON.stringify({symbol: document.getElementById("analyze-symbol").value})});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      result.hidden = true;
      failure.textContent = `Error ${response.status}: ${body.detail?.message ?? "respuesta no válida"}`
        + (body.request_id ? ` · request_id ${body.request_id}` : "");
      failure.hidden = false;
      return;
    }
    text("analyze-summary", body.summary);
    text("analyze-meta", `${body.symbol} · ${body.provider} · ${body.model} · ${millis.format(body.latency_ms)} ms · request_id ${body.request_id}`);
    result.hidden = false;
  } catch (error) {
    result.hidden = true;
    failure.textContent = "Error de red: el servicio no respondió.";
    failure.hidden = false;
  } finally {
    button.disabled = false;
    renderOperation();
  }
}

document.getElementById("analyze-form").addEventListener("submit", analyze);
document.getElementById("ops-refresh").addEventListener("click", renderOperation);

fetch("/api/v1/snapshot", {headers: {Accept: "application/json"}})
  .then(response => {
    if (!response.ok) throw new Error("Informe no disponible");
    return response.json();
  })
  .then(render)
  .catch(() => {
    document.getElementById("status").dataset.error = "true";
    text("status", "Informe no disponible. Comprueba el estado del servicio.");
  })
  .finally(renderOperation);
