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
