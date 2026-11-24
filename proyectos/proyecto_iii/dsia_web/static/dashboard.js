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

function aiStatus(checks) {
  // R9: proveedor declarado, configuración validada al arrancar y resultado de la última llamada real.
  if (!checks.ai_provider) return "";
  const lastCall = checks.ai_last_call === "never" ? "sin llamadas"
    : checks.ai_last_call === "ok" ? "correcta"
      : `fallida (${String(checks.ai_last_call).replace("failing:", "")})`;
  return `IA ${checks.ai_provider} · configuración ${checks.ai_config === "ok" ? "válida" : "no válida"}`
    + ` · última llamada ${lastCall}`;
}

// Grafo del lote: topología fija (siempre los mismos 8 nodos y en el mismo orden) y estado de cada nodo
// derivado solo de los eventos observados en /api/v1/pipeline y del run_id que sirve /health.
const FLOW = [
  {id: "source", stages: ["generate_bars", "download_bars"], label: "Datos"},
  {id: "validate_input", stages: ["validate_input"], label: "Validar entrada"},
  {id: "prepare", stages: ["prepare"], label: "Preparar"},
  {id: "train", stages: ["train"], label: "Entrenar"},
  {id: "holdout", stages: ["holdout"], label: "Holdout"},
  {id: "infer_snapshot", stages: ["infer_snapshot"], label: "Inferir"},
  {id: "publish_snapshot", stages: ["publish_snapshot"], label: "Publicar snapshot"},
  {id: "serve", stages: [], label: "Servir API"},
];
const MODEL_STAGES = ["prepare", "train", "holdout"];
const FLOW_STATES = {
  succeeded: "completada", failed: "fallida", started: "iniciada sin cierre",
  pending: "pendiente", skipped: "omitida en este lote", reused: "reutilizada",
  unreached: "no alcanzada", truncated: "fuera de la ventana", unknown: "sin eventos",
  serving: "sirve el lote publicado", degraded: "sirve el lote · IA degradada",
  mismatch: "sirve otro run_id", unverified: "run_id sin verificar", down: "sin informe válido",
};
const OBSERVED = ["succeeded", "failed", "started", "serving", "degraded", "mismatch", "unverified"];
let flowSelected = null;

const flowIndex = stage => FLOW.findIndex(node => node.stages.includes(stage));

function lastRun(events) {
  // > Un lote nuevo empieza cuando una etapa igual o anterior a la más avanzada vuelve a «started».
  let start = 0;
  let highest = -1;
  events.forEach((event, position) => {
    const index = flowIndex(event.stage);
    if (index < 0) return;
    if (event.status === "started" && index <= highest) {
      start = position;
      highest = -1;
    }
    highest = Math.max(highest, index);
  });
  return {events: events.slice(start), earlier: start};
}

function pipelineModel({journal, events = [], limit = 20, skipped = 0, servedRunId = null, health = "unavailable"}) {
  const run = journal === "ok" ? lastRun(events) : {events: [], earlier: 0};
  const known = run.events.filter(event => flowIndex(event.stage) >= 0);
  const unknownStages = [...new Set(run.events.filter(event => flowIndex(event.stage) < 0).map(event => event.stage))];
  const first = known[0];
  const sawModel = known.some(event => MODEL_STAGES.includes(event.stage));
  const startsCleanly = Boolean(first) && first.status === "started"
    && (FLOW[0].stages.includes(first.stage) || first.stage === "validate_input");
  // > from-run (refresco de un modelo ya entrenado): empieza en validate_input y no entrena.
  const refresh = startsCleanly && first.stage === "validate_input" && !sawModel;
  const truncated = known.length > 0 && (!startsCleanly || (first.stage === "validate_input" && sawModel));
  const firstIndex = first ? flowIndex(first.stage) : FLOW.length;
  const lastIndex = known.length ? Math.max(...known.map(event => flowIndex(event.stage))) : -1;
  const nodes = [];
  let failedAt = -1;
  let openAt = -1;
  FLOW.slice(0, -1).forEach((node, index) => {
    const seen = run.events.filter(event => node.stages.includes(event.stage));
    const latest = seen[seen.length - 1];
    let state;
    let reason = "";
    if (journal !== "ok" || !known.length) {
      state = "unknown";
      reason = journal === "missing" ? "El servicio no tiene journal configurado (DSIA_JOURNAL)."
        : journal === "unavailable" ? "El journal existe pero no se pudo leer."
          : "El journal no contiene eventos de etapas reconocidas.";
    } else if (latest) {
      state = ["succeeded", "failed", "started"].includes(latest.status) ? latest.status : "unknown";
      if (state === "failed") failedAt = index;
      if (state === "started") {
        openAt = index;
        reason = "Hay un «started» sin «succeeded» ni «failed»: lote en curso o interrumpido.";
      }
    } else if (truncated && index < firstIndex) {
      state = "truncated";
      reason = `Sus eventos quedaron fuera de los últimos ${limit} eventos o de los 64 KiB leídos del journal.`;
    } else if (failedAt >= 0) {
      state = "unreached";
      reason = "Una etapa anterior falló y el lote se detuvo.";
    } else if (refresh && MODEL_STAGES.includes(node.id)) {
      state = "reused";
      reason = "Refresco (from-run): se reutiliza el modelo ya entrenado, sin volver a entrenar ni tocar el holdout.";
    } else if (openAt >= 0 || index > lastIndex) {
      state = "pending";
      reason = "Aún no hay eventos de esta etapa en el lote observado.";
    } else {
      state = "skipped";
      reason = node.id === "source" ? "Este lote parte de datos ya descargados."
        : node.id === "validate_input" ? "La demo sintética genera sus datos y no registra esta etapa."
          : "El lote no registró esta etapa.";
    }
    nodes.push({...node, state, reason, events: seen});
  });
  // > Solo cuenta como publicado un publish_snapshot «succeeded»: el «started» también lleva run_id.
  const publish = nodes[nodes.length - 1].events.filter(event => event.run_id && event.status === "succeeded");
  const runId = publish.length ? publish[publish.length - 1].run_id : null;
  let serve;
  let serveReason;
  if (health === "unavailable" || !servedRunId) {
    serve = "down";
    serveReason = "/health no confirma un snapshot válido cargado.";
  } else if (!runId) {
    serve = "unverified";
    serveReason = failedAt >= 0
      ? "El último lote falló antes de publicar: el servicio sigue con el snapshot ya cargado, que no se puede atribuir a este lote."
      : "El lote observado no registró publish_snapshot en succeeded: no se puede comprobar qué lote se sirve.";
  } else if (runId !== servedRunId) {
    serve = "mismatch";
    serveReason = "El servicio sirve un snapshot distinto del último publicado en el journal.";
  } else {
    serve = health === "degraded" ? "degraded" : "serving";
    serveReason = health === "degraded" ? "El snapshot coincide; /health marca degradado el proveedor de IA."
      : "El run_id de /health coincide con el que publicó el lote.";
  }
  nodes.push({...FLOW[FLOW.length - 1], state: serve, reason: serveReason, events: [], runId, servedRunId});
  const alerts = [];
  if (journal === "missing") alerts.push("Journal no configurado (DSIA_JOURNAL): las etapas no tienen eventos; el servicio se comprueba con /health.");
  if (journal === "unavailable") alerts.push("Journal ilegible o no disponible: no se pueden mostrar las etapas.");
  if (skipped) alerts.push(`${skipped} líneas del journal no se pudieron interpretar y se descartaron.`);
  if (truncated) alerts.push("Lote truncado: faltan sus primeros eventos en la ventana leída del journal.");
  if (run.earlier) alerts.push("La ventana incluye eventos de un lote anterior; el grafo muestra el último.");
  if (unknownStages.length) alerts.push(`Etapas no reconocidas en el journal: ${unknownStages.join(", ")}.`);
  if (nodes.some(node => node.state === "reused")) alerts.push("Refresco con un modelo ya entrenado: preparar, entrenar y holdout se reutilizan.");
  if (serve === "mismatch") alerts.push(`run_id discrepante: el servicio sirve ${servedRunId} y el lote publicó ${runId}.`);
  if (serve === "unverified" && journal === "ok") alerts.push("run_id desconocido: el lote no registró la publicación del snapshot.");
  return {nodes, alerts, runId, servedRunId, refresh, truncated};
}

function eventLine(event) {
  const parts = [event.status];
  if (event.timestamp) parts.push(`${event.timestamp.slice(11, 19)} UTC`);
  if (event.duration_ms !== undefined) parts.push(`${millis.format(event.duration_ms)} ms`);
  if (event.rows !== undefined) parts.push(`${event.rows} filas`);
  if (event.symbols !== undefined) parts.push(`${event.symbols} símbolos`);
  if (event.error_type) parts.push(`error ${event.error_type}`);
  if (event.input_sha256) parts.push(`sha256 ${String(event.input_sha256).slice(0, 12)}…`);
  if (event.run_id) parts.push(`run_id ${event.run_id}`);
  return `${event.stage} · ${parts.join(" · ")}`;
}

function nodeSummary(node) {
  const latest = node.events[node.events.length - 1];
  const duration = latest?.duration_ms === undefined ? "" : ` · ${millis.format(latest.duration_ms)} ms`;
  return FLOW_STATES[node.state] + (node.state === "succeeded" ? duration : "");
}

function replaceIfChanged(container, parts) {
  // > Las regiones aria-live se releen enteras al sustituirse: solo se tocan si cambia el texto.
  const next = parts.map(part => part.textContent).join("\n");
  if (container.dataset.rendered === next) return;
  container.dataset.rendered = next;
  container.replaceChildren(...parts);
}

function renderFlowDetail(model) {
  const detail = document.getElementById("ops-graph-detail");
  const node = model.nodes.find(item => item.id === flowSelected);
  if (!node) {
    replaceIfChanged(detail, [element("p", "Elige una etapa para ver sus eventos.", "note")]);
    return;
  }
  const heading = element("h4", `${node.label} · ${FLOW_STATES[node.state]}`);
  const parts = [heading];
  if (node.reason) parts.push(element("p", node.reason, "note"));
  if (node.id === "serve") {
    const facts = element("dl", undefined, "provenance");
    facts.append(element("dt", "run_id servido (/health)"), element("dd", node.servedRunId ?? "—"),
      element("dt", "run_id publicado (journal)"), element("dd", node.runId ?? "—"));
    parts.push(facts);
  } else {
    parts.push(element("p", `Eventos del journal: ${node.stages.join(" o ")}`, "note"));
    const list = element("ul", undefined, "flow-events");
    list.append(...(node.events.length ? node.events.map(event => element("li", eventLine(event), "mono"))
      : [element("li", "Sin eventos observados.")]));
    parts.push(list);
  }
  replaceIfChanged(detail, parts);
}

function selectFlowNode(model, id) {
  flowSelected = id;
  document.querySelectorAll("#ops-graph .flow-node").forEach(button => {
    const active = button.dataset.node === id;
    if (active) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
    button.tabIndex = active ? 0 : -1;
  });
  renderFlowDetail(model);
}

function renderFlow(model) {
  const graph = document.getElementById("ops-graph");
  const hadFocus = graph.contains(document.activeElement) ? document.activeElement.dataset.node : null;
  if (!model.nodes.some(node => node.id === flowSelected)) flowSelected = null;
  const items = model.nodes.map((node, index) => {
    const item = element("li");
    item.dataset.state = node.state;
    const button = element("button", undefined, "flow-node");
    button.type = "button";
    button.dataset.node = node.id;
    button.dataset.state = node.state;
    button.setAttribute("aria-controls", "ops-graph-detail");
    if (node.id === flowSelected) button.setAttribute("aria-current", "true");
    // > La parada de tabulación sigue al nodo que tenía el foco antes del refresco.
    button.tabIndex = node.id === (hadFocus ?? flowSelected ?? model.nodes[0].id) ? 0 : -1;
    button.append(element("span", `${index + 1}`, "flow-step"), element("span", node.label, "flow-label"),
      element("span", nodeSummary(node), "flow-state"));
    button.addEventListener("click", () => selectFlowNode(model, node.id));
    item.append(button);
    const next = model.nodes[index + 1];
    if (next) {
      // > Conector decorativo en SVG: el orden ya lo comunica la lista ordenada.
      const edge = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      edge.setAttribute("viewBox", "0 0 24 24");
      edge.setAttribute("aria-hidden", "true");
      edge.setAttribute("class", "edge");
      edge.dataset.state = ["failed", "mismatch", "down"].includes(next.state) ? "bad"
        : ["started", "unverified", "degraded"].includes(next.state) ? "warn"
          : OBSERVED.includes(next.state) ? "on" : "off";
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", "M2 12h18M14 6l6 6-6 6");
      edge.append(path);
      item.append(edge);
    }
    return item;
  });
  graph.replaceChildren(...items);
  replaceIfChanged(document.getElementById("ops-flow-alerts"), model.alerts.map(alert => element("li", alert)));
  renderFlowDetail(model);
  if (hadFocus) graph.querySelector(`[data-node="${hadFocus}"]`)?.focus();
}

document.getElementById("ops-graph").addEventListener("keydown", event => {
  const buttons = [...event.currentTarget.querySelectorAll(".flow-node")];
  const current = buttons.indexOf(document.activeElement);
  if (current < 0) return;
  const moves = {ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1};
  let target = null;
  if (event.key in moves) target = Math.min(buttons.length - 1, Math.max(0, current + moves[event.key]));
  else if (event.key === "Home") target = 0;
  else if (event.key === "End") target = buttons.length - 1;
  if (target === null) return;
  event.preventDefault();
  buttons.forEach((button, index) => { button.tabIndex = index === target ? 0 : -1; });
  buttons[target].focus();
});

async function renderOperation() {
  // 20 eventos: el lote con Alpaca registra 14 (de download_bars a publish_snapshot) y caben todos.
  const [health, metrics, pipeline] = await Promise.all(
    ["/health", "/api/v1/metrics", "/api/v1/pipeline?limit=20"].map(url => getJSON(url).catch(() => null)));
  const checks = health?.body?.checks ?? {};
  const state = health?.ok && ["ready", "degraded"].includes(health.body?.status) ? health.body.status : "unavailable";
  const status = document.getElementById("ops-status");
  status.textContent = state === "ready" ? "Operativo (200)"
    : state === "degraded" ? "Degradado (200)"
      : `Sin informe válido (${health ? health.status : "sin respuesta"})`;
  status.dataset.state = state;
  text("ops-ai", aiStatus(checks));
  text("ops-run", health?.body?.run_id ?? "—");
  text("ops-as-of", checks.as_of ?? "—");
  text("ops-age", checks.snapshot_age_days === null || checks.snapshot_age_days === undefined
    ? "—" : `${checks.snapshot_age_days} días`);
  // Versión del III y commit desplegado (RENDER_GIT_COMMIT en Render; DSIA_COMMIT o «local» fuera de él;
  // «invalid» si la variable no es un hash).
  text("ops-version", health?.body?.version ? `v${health.body.version} · commit ${health.body.commit}` : "");
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
  renderFlow(pipelineModel({
    journal: pipeline?.ok ? "ok" : pipeline?.status === 404 ? "missing" : "unavailable",
    events, limit: 20, skipped: pipeline?.ok ? pipeline.body.skipped_lines : 0,
    servedRunId: health?.ok ? health.body.run_id ?? null : null, health: state,
  }));
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
