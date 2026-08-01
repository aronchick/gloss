const state = { view: "summary", data: null, filter: "" };

const rows = document.querySelector("#leaderboard-rows");
const shell = document.querySelector("#board-shell");
const status = document.querySelector("#board-status");
const updated = document.querySelector("#updated-at");
const notice = document.querySelector("#comparability");
const filter = document.querySelector("#model-filter");
const assistedBoard = document.querySelector("#assisted-board");
const assistedList = document.querySelector("#assisted-list");
const assistedCount = document.querySelector("#assisted-count");

const text = (tag, className, value) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = value;
  return node;
};

const scoreCell = (entry, tier) => {
  const cell = document.createElement("td");
  cell.className = "score-cell";
  const metric = entry.tier_scores[`level_${tier}`];
  if (!metric) {
    cell.classList.add("score-empty");
    cell.textContent = "—";
  } else {
    const displayed = metric.official_score ?? metric.provisional_score;
    cell.textContent = displayed == null ? "—" : Number(displayed).toFixed(4);
    cell.title = `${metric.submission_count}/3 occupied slot${metric.submission_count === 1 ? "" : "s"}${metric.official_score == null ? " · provisional" : " · official three-run mean"}${metric.robustness_score == null ? "" : ` · robustness ${Number(metric.robustness_score).toFixed(4)}`}`;
  }
  return cell;
};

const matching = (entry) => `${entry.model_display_name} ${entry.model_revision_display}`.toLowerCase().includes(state.filter);

function renderRows() {
  rows.replaceChildren();
  const entries = (state.data?.entries || []).filter(matching);
  entries.forEach((entry, index) => {
    const row = document.createElement("tr");
    row.append(text("td", "rank", String(index + 1).padStart(2, "0")));

    const model = document.createElement("td");
    model.className = "model-cell";
    model.append(text("strong", "", entry.model_display_name), text("span", "", entry.model_revision_display));
    row.append(model, scoreCell(entry, 1), scoreCell(entry, 2), scoreCell(entry, 3));

    const aggregate = document.createElement("td");
    aggregate.className = "aggregate-cell";
    const official = entry.aggregate_score;
    aggregate.append(text("span", "score-value", official == null ? "PROV" : Number(official).toFixed(4)));
    const rail = text("div", "score-rail", "");
    const fill = document.createElement("span");
    fill.style.width = `${official == null ? 0 : Math.max(0, Math.min(1, Number(official))) * 100}%`;
    rail.append(fill);
    aggregate.append(rail);
    row.append(aggregate);

    const environment = text("td", "environment-cell", entry.scoring_cohort_id.slice(0, 19));
    environment.title = `${entry.scoring_cohort_id} · ${entry.verification_label}`;
    row.append(environment);
    rows.append(row);
  });

  if (!entries.length) {
    status.hidden = false;
    status.textContent = state.filter ? "No model matches that filter." : "No eligible grading-verified runs have been published yet.";
    shell.hidden = true;
  } else {
    status.hidden = true;
    shell.hidden = false;
  }

  const assisted = (state.data?.human_assisted_entries || []).filter(matching);
  assistedList.replaceChildren();
  assisted.forEach((entry) => {
    const item = text("div", "assisted-item", "");
    item.append(text("strong", "", `${entry.model_display_name} · ${entry.model_revision_display}`));
    item.append(text("span", "", `${entry.aggregate_score == null ? "Provisional" : Number(entry.aggregate_score).toFixed(4)} · Level ${entry.tier}`));
    assistedList.append(item);
  });
  assistedCount.textContent = assisted.length ? `(${assisted.length})` : "";
  assistedBoard.hidden = assisted.length === 0;
}

async function loadLeaderboard() {
  status.hidden = false;
  shell.hidden = true;
  status.textContent = "Reading the latest verified runs…";
  try {
    const response = await fetch(`/v1/leaderboard?view=${state.view}`, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Leaderboard returned ${response.status}`);
    state.data = await response.json();
    const timestamp = new Date(state.data.updated_at);
    updated.textContent = `Updated ${timestamp.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}`;
    notice.textContent = state.data.comparability_notice;
    renderRows();
  } catch (error) {
    status.hidden = false;
    status.textContent = "The leaderboard could not be loaded. Check the service status and try again.";
    console.error(error);
  }
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    state.view = button.dataset.view;
    document.querySelectorAll("[data-view]").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
    loadLeaderboard();
  });
});

filter.addEventListener("input", () => {
  state.filter = filter.value.trim().toLowerCase();
  renderRows();
});

loadLeaderboard();
