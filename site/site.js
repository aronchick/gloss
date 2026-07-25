const xray = document.querySelector(".xray");
const xrayButtons = [...document.querySelectorAll("[data-xray-target]")];
const xrayPanels = [...document.querySelectorAll("[data-xray-panel]")];
let xrayTimer;

function showXrayLayer(layer, { userInitiated = false } = {}) {
  if (!xray) return;
  xray.dataset.xray = layer;
  for (const button of xrayButtons) {
    const active = button.dataset.xrayTarget === layer;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  }
  for (const panel of xrayPanels) {
    panel.hidden = panel.dataset.xrayPanel !== layer;
  }
  if (userInitiated) window.clearTimeout(xrayTimer);
}

for (const button of xrayButtons) {
  button.addEventListener("click", () => showXrayLayer(button.dataset.xrayTarget, { userInitiated: true }));
}

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
if (!reducedMotion) {
  xrayTimer = window.setTimeout(() => showXrayLayer("package"), 1500);
}

const evidenceBindings = {
  "candidate-checks": (data) => data.candidate_checks.total,
  "visual-checks": (data) => data.candidate_checks.visual_render,
  "inside-file-checks": (data) => data.candidate_checks.inside_file,
  "inside-file-percent": (data) => data.candidate_checks.inside_file_percent,
  "positive-passed": (data) => data.operator_evidence.positive_controls_passed,
  "positive-total": (data) => data.operator_evidence.positive_controls,
  "mutants-detected": (data) => data.operator_evidence.single_fault_mutations_detected,
  "mutants-total": (data) => data.operator_evidence.single_fault_mutations,
};

fetch("/evidence/preview-v1.json")
  .then((response) => {
    if (!response.ok) throw new Error(`Evidence request failed: ${response.status}`);
    return response.json();
  })
  .then((data) => {
    document.documentElement.dataset.evidenceId = data.evidence_id;
    for (const [key, readValue] of Object.entries(evidenceBindings)) {
      for (const node of document.querySelectorAll(`[data-evidence="${key}"]`)) {
        node.textContent = String(readValue(data));
      }
    }
  })
  .catch(() => {
    document.documentElement.dataset.evidenceId = "fallback-copy";
  });

const comparativeChart = document.querySelector("[data-comparative-chart]");
const comparativeMetrics = [
  ["local_fidelity_percent", "Local fidelity"],
  ["mean_visual_ssim_percent", "Visual SSIM"],
  ["native_weighted_pass_percent", "Native pass"],
];

function comparativeCell(value, label) {
  const cell = document.createElement("div");
  cell.className = "comparison-metric";
  cell.setAttribute("aria-label", `${label}: ${value.toFixed(2)} percent`);

  const number = document.createElement("strong");
  number.textContent = value.toFixed(2);
  const percent = document.createElement("sup");
  percent.textContent = "%";
  number.append(percent);

  const track = document.createElement("span");
  track.className = "comparison-track";
  const bar = document.createElement("i");
  bar.style.setProperty("--score", String(value));
  track.append(bar);
  cell.append(number, track);
  return cell;
}

function renderComparative(data) {
  if (!comparativeChart) return;
  comparativeChart.replaceChildren();

  const header = document.createElement("div");
  header.className = "comparison-row comparison-row-head";
  const pathHeading = document.createElement("span");
  pathHeading.textContent = "Generation path";
  header.append(pathHeading);
  for (const [, label] of comparativeMetrics) {
    const metricHeading = document.createElement("span");
    metricHeading.textContent = label;
    header.append(metricHeading);
  }
  comparativeChart.append(header);

  for (const path of data.paths) {
    const row = document.createElement("div");
    row.className = `comparison-row comparison-row-${path.path_id.split("-")[0]}`;

    const identity = document.createElement("div");
    identity.className = "comparison-identity";
    const label = document.createElement("strong");
    label.textContent = path.label;
    const runCount = document.createElement("span");
    runCount.textContent = `${path.runs.length} seeded runs`;
    identity.append(label, runCount);
    row.append(identity);

    for (const [key, metricLabel] of comparativeMetrics) {
      row.append(comparativeCell(path.mean_metrics[key], metricLabel));
    }
    comparativeChart.append(row);
  }

  for (const node of document.querySelectorAll("[data-comparative-label]")) {
    node.textContent = data.disclosure.verification_label;
  }
  const cohort = data.cohort.scoring_cohort_id.replace("sha256:", "");
  for (const node of document.querySelectorAll("[data-cohort-short]")) {
    node.textContent = cohort.slice(0, 12);
    node.setAttribute("title", data.cohort.scoring_cohort_id);
  }
  for (const node of document.querySelectorAll("[data-comparative-runs]")) {
    node.textContent = String(data.totals.runs);
  }
  for (const node of document.querySelectorAll("[data-comparative-slides]")) {
    node.textContent = String(data.totals.slides);
  }
}

fetch("/evidence/comparative-v1-summary.json")
  .then((response) => {
    if (!response.ok) throw new Error(`Comparative summary request failed: ${response.status}`);
    return response.json();
  })
  .then(renderComparative)
  .catch(() => {
    if (comparativeChart) {
      comparativeChart.textContent = "Comparative summary unavailable. Open the public JSON evidence.";
    }
  });

const copyButton = document.querySelector("[data-copy-command]");
const copyStatus = document.querySelector("[data-copy-status]");
const command = document.querySelector(".command-block code");

if (copyButton && command) {
  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(command.textContent.trim());
      copyButton.textContent = "Copied";
      if (copyStatus) copyStatus.textContent = "Commands copied to clipboard.";
      window.setTimeout(() => {
        copyButton.textContent = "Copy";
        if (copyStatus) copyStatus.textContent = "";
      }, 1800);
    } catch {
      if (copyStatus) copyStatus.textContent = "Select the commands and copy them manually.";
    }
  });
}
