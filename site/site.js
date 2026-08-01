const inspector = document.querySelector("[data-inspector]");
const inspectorButtons = [...document.querySelectorAll("[data-inspect]")];
const objectName = document.querySelector("[data-object-name]");
const objectDetail = document.querySelector("[data-object-detail]");
const objectType = document.querySelector("[data-object-type]");

const inspectorContent = {
  title: {
    name: "Title placeholder",
    detail: "Editable text · inherited from the Title Slide layout",
    type: "Placeholder",
  },
  art: {
    name: "Image + three shapes",
    detail: "Independent objects · crop · z-order · transparency · shadow",
    type: "Picture / shapes",
  },
  footer: {
    name: "Master footer",
    detail: "Slide number field · rule · repeated GLOSS label",
    type: "Master objects",
  },
};

function inspectObject(name) {
  const content = inspectorContent[name];
  if (!inspector || !content) return;
  inspector.dataset.inspector = name;
  if (objectName) objectName.textContent = content.name;
  if (objectDetail) objectDetail.textContent = content.detail;
  if (objectType) objectType.textContent = content.type;
  for (const button of inspectorButtons) {
    const active = button.dataset.inspect === name;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  }
}

for (const button of inspectorButtons) {
  button.addEventListener("click", () => inspectObject(button.dataset.inspect));
}

const copyButton = document.querySelector("[data-copy-check]");
const copyStatus = document.querySelector("[data-copy-status]");
const checkCommand = "uv run gloss check edited.pptx";

if (copyButton) {
  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(checkCommand);
      copyButton.textContent = "Copied";
      if (copyStatus) copyStatus.textContent = "Command copied to clipboard.";
      window.setTimeout(() => {
        copyButton.textContent = "Copy command";
        if (copyStatus) copyStatus.textContent = "";
      }, 1800);
    } catch {
      if (copyStatus) copyStatus.textContent = "Select the command and copy it manually.";
    }
  });
}

const slideCases = [...document.querySelectorAll("[data-slide]")];
const slideLinks = [...document.querySelectorAll("[data-slide-link]")];
const currentSlide = document.querySelector("[data-current-slide]");

function setCurrentSlide(number) {
  if (currentSlide) currentSlide.textContent = number;
  for (const link of slideLinks) {
    const active = link.dataset.slideLink === number;
    link.classList.toggle("is-active", active);
    if (active) link.setAttribute("aria-current", "true");
    else link.removeAttribute("aria-current");
  }
}

if ("IntersectionObserver" in window) {
  const ratios = new Map();
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        ratios.set(entry.target, entry.isIntersecting ? entry.intersectionRatio : 0);
      }
      const visible = [...ratios.entries()].sort((a, b) => b[1] - a[1])[0];
      if (visible && visible[1] > 0) setCurrentSlide(visible[0].dataset.slide);
    },
    { rootMargin: "-18% 0px -52% 0px", threshold: [0, 0.1, 0.25, 0.5, 0.75] },
  );
  for (const slide of slideCases) observer.observe(slide);
}
