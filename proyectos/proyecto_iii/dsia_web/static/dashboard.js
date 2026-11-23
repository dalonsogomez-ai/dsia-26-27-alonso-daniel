"use strict";

const text = (id, value) => { document.getElementById(id).textContent = value; };
const percent = new Intl.NumberFormat("es-ES", {style: "percent", maximumFractionDigits: 2});
const decimal = new Intl.NumberFormat("es-ES", {minimumFractionDigits: 4, maximumFractionDigits: 4});
const modelNames = {dummy: "Dummy", ridge: "Ridge", swarm: "Swarm sklearn"};
const dataNames = {synthetic: "Simulación sintética", alpaca: "Histórico Alpaca", local: "Histórico local"};

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
  renderPredictions(predictions);
  document.getElementById("filter").addEventListener("input", () => renderPredictions(predictions));
  document.getElementById("results").hidden = false;
}

fetch("/api/v1/snapshot", {headers: {Accept: "application/json"}})
  .then(response => {
    if (!response.ok) throw new Error("Informe no disponible");
    return response.json();
  })
  .then(render)
  .catch(() => {
    document.getElementById("status").dataset.error = "true";
    text("status", "Informe no disponible. Comprueba el estado del servicio.");
  });
