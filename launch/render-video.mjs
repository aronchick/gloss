#!/usr/bin/env node

import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const launchDir = dirname(fileURLToPath(import.meta.url));
const root = resolve(launchDir, "..");
const evidencePath = join(root, "site/evidence/preview-v1.json");
const outputPath = join(root, "site/media/gloss-launch.mp4");
const posterPath = join(root, "site/media/gloss-launch-poster.png");
const evidence = JSON.parse(readFileSync(evidencePath, "utf8"));

const width = 1080;
const height = 1080;
const fps = 30;
const duration = 21;
const frameCount = fps * duration;
const colors = {
  canvas: "#f4f6fa",
  paper: "#ffffff",
  ink: "#171a22",
  muted: "#68717f",
  rule: "#c9ced8",
  orange: "#d35230",
  orangeSoft: "#f7ded5",
  blue: "#2859d6",
  blueSoft: "#dfe8ff",
  proof: "#b7f36b",
};

function commandExists(command) {
  return spawnSync("sh", ["-c", `command -v ${command}`], { stdio: "ignore" }).status === 0;
}

function requireCommand(command) {
  if (!commandExists(command)) {
    throw new Error(`${command} is required to render the launch video`);
  }
}

function clamp(value, min = 0, max = 1) {
  return Math.min(max, Math.max(min, value));
}

function ease(value) {
  const t = clamp(value);
  return 1 - (1 - t) ** 3;
}

function fadeInOut(t, start, end, edge = 0.4) {
  return clamp((t - start) / edge) * clamp((end - t) / edge);
}

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function svgText(text, x, y, options = {}) {
  const {
    size = 48,
    weight = 700,
    fill = colors.ink,
    anchor = "start",
    family = "Aptos Display, Arial Narrow, Segoe UI, sans-serif",
    spacing = 0,
    opacity = 1,
  } = options;
  return `<text x="${x}" y="${y}" fill="${fill}" font-family="${family}" font-size="${size}" font-weight="${weight}" text-anchor="${anchor}" letter-spacing="${spacing}" opacity="${opacity}">${escapeXml(text)}</text>`;
}

function mono(text, x, y, options = {}) {
  return svgText(text, x, y, {
    family: "SFMono-Regular, Consolas, Liberation Mono, monospace",
    size: 22,
    weight: 700,
    spacing: 1.5,
    ...options,
  });
}

function baseSvg(body, background = colors.canvas) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <rect width="${width}" height="${height}" fill="${background}"/>
    ${body}
  </svg>`;
}

function frameIntro(t) {
  const p = ease(t / 1.5);
  const opacity = fadeInOut(t, 0, 2, 0.35);
  const offset = 40 * (1 - p);
  return baseSvg(`
    <g opacity="${opacity}" transform="translate(0 ${offset})">
      ${mono("OPEN POWERPOINT BENCHMARK", 72, 112, { fill: colors.orange })}
      ${svgText("Gloss", 72, 480, { size: 230, weight: 780 })}
      <rect x="74" y="530" width="${510 * p}" height="14" fill="${colors.orange}"/>
      ${svgText("Same file.", 76, 655, { size: 78, weight: 720 })}
      ${svgText("Two truths.", 76, 742, { size: 78, weight: 720, fill: colors.blue })}
      ${mono("LOOKS RIGHT  ↔  BUILT RIGHT", 76, 928, { fill: colors.muted })}
    </g>
  `);
}

function frameTwoLayers(t) {
  const local = t - 2;
  const opacity = fadeInOut(t, 2, 9.2, 0.35);
  const total = evidence.candidate_checks.total;
  const visual = evidence.candidate_checks.visual_render;
  const inside = evidence.candidate_checks.inside_file;
  const progress = ease(local / 4.8);
  const rows = [
    { label: "INSIDE THE FILE", count: inside, color: colors.blue, y: 478 },
    { label: "ON THE CANVAS", count: visual, color: colors.orange, y: 682 },
  ];
  const rowMarkup = rows.map((row, index) => {
    const stagger = ease((local - index * 0.32) / 3.4);
    const barWidth = (row.count / inside) * 760 * stagger;
    const count = Math.round(row.count * progress);
    return `
      ${mono(row.label, 78, row.y - 28, { fill: colors.muted, size: 19 })}
      <rect x="78" y="${row.y}" width="760" height="88" fill="#e2e6ed"/>
      <rect x="78" y="${row.y}" width="${barWidth}" height="88" fill="${row.color}"/>
      ${svgText(String(count), 952, row.y + 67, { size: 62, weight: 760, anchor: "end" })}
    `;
  }).join("");
  return baseSvg(`
    <g opacity="${opacity}">
      ${mono("GLOSS / CANDIDATE HARNESS", 78, 90, { fill: colors.orange })}
      ${svgText(`${total} ways to ask`, 78, 230, { size: 100, weight: 760 })}
      ${svgText("if a deck is real.", 78, 332, { size: 100, weight: 760 })}
      ${rowMarkup}
      ${mono("CANDIDATE CHECK COUNTS · NOT MODEL SCORES", 78, 966, { fill: colors.muted, size: 18 })}
    </g>
  `);
}

function frameTwist(t) {
  const local = t - 9.2;
  const opacity = fadeInOut(t, 9.2, 11, 0.2);
  const p = ease(local / 1.2);
  const percent = Math.round(evidence.candidate_checks.inside_file_percent * p);
  return baseSvg(`
    <g opacity="${opacity}">
      <rect x="0" y="0" width="${width}" height="${height}" fill="${colors.ink}"/>
      <rect x="68" y="68" width="944" height="944" fill="none" stroke="#49505d" stroke-width="2"/>
      ${mono("THE ARTIFACT TWIST", 92, 130, { fill: colors.proof })}
      ${svgText(`${percent}%`, 540, 550, { size: 310, weight: 790, fill: colors.paper, anchor: "middle" })}
      ${svgText("of candidate checks", 540, 680, { size: 70, weight: 700, fill: colors.paper, anchor: "middle" })}
      ${svgText("live inside the file.", 540, 760, { size: 70, weight: 700, fill: colors.blueSoft, anchor: "middle" })}
      ${mono("LOOKING RIGHT ISN’T BEING EDITABLE", 540, 927, { fill: "#aab2c0", anchor: "middle", size: 19 })}
    </g>
  `, colors.ink);
}

function frameMethods(t) {
  const local = t - 11;
  const opacity = fadeInOut(t, 11, 18.2, 0.3);
  const methods = evidence.verification_methods.filter((method) => method.id !== "visual_ssim");
  const max = Math.max(...methods.map((method) => method.count));
  const rows = methods.map((method, index) => {
    const y = 390 + index * 120;
    const p = ease((local - index * 0.2) / 3.5);
    const barWidth = (method.count / max) * 670 * p;
    return `
      ${mono(`${String(index + 1).padStart(2, "0")}  ${method.public_label.toUpperCase()}`, 76, y - 18, { fill: colors.muted, size: 18 })}
      <rect x="76" y="${y}" width="670" height="58" fill="#e0e4ec"/>
      <rect x="76" y="${y}" width="${barWidth}" height="58" fill="${index === 0 ? colors.blue : "#5c7edd"}"/>
      ${svgText(String(Math.round(method.count * p)), 944, y + 48, { size: 48, weight: 760, anchor: "end" })}
    `;
  }).join("");
  return baseSvg(`
    <g opacity="${opacity}">
      ${mono("BUILT RIGHT / INSIDE-FILE CHECKS", 76, 82, { fill: colors.blue })}
      ${svgText("What the screenshot", 76, 202, { size: 88, weight: 760 })}
      ${svgText("cannot tell you.", 76, 292, { size: 88, weight: 760 })}
      ${rows}
      ${mono(`${evidence.candidate_checks.inside_file} CANDIDATE CHECKS · ${evidence.operator_evidence.operators} MUTATION OPERATORS`, 76, 1020, { fill: colors.muted, size: 17 })}
    </g>
  `);
}

function frameEnd(t) {
  const local = t - 18.2;
  const p = ease(local / 1.1);
  const opacity = clamp(local / 0.25);
  return baseSvg(`
    <g opacity="${opacity}" transform="translate(0 ${24 * (1 - p)})">
      ${mono("OPEN TECHNICAL PREVIEW", 74, 92, { fill: colors.proof })}
      ${svgText("Gloss", 72, 388, { size: 230, weight: 790, fill: colors.paper })}
      <rect x="76" y="438" width="${530 * p}" height="13" fill="${colors.orange}"/>
      ${svgText("Generative Layout &", 76, 545, { size: 50, weight: 690, fill: "#cdd3df" })}
      ${svgText("OOXML Scoring System", 76, 607, { size: 50, weight: 690, fill: "#cdd3df" })}
      <line x1="76" y1="700" x2="1004" y2="700" stroke="#4b5361" stroke-width="2"/>
      ${svgText(`${evidence.operator_evidence.single_fault_mutations_detected} / ${evidence.operator_evidence.single_fault_mutations}`, 76, 795, { size: 78, weight: 780, fill: colors.proof })}
      ${mono("GENERATED SINGLE-FAULT MUTATIONS DETECTED", 76, 837, { fill: "#aeb6c4", size: 17 })}
      ${svgText("gloss.tools", 76, 982, { size: 72, weight: 760, fill: colors.paper })}
      ${mono("BUILD IT WITH US ON GITHUB  ↗", 1004, 982, { fill: colors.orange, anchor: "end", size: 17 })}
    </g>
  `, colors.ink);
}

function renderFrame(time) {
  if (time < 2) return frameIntro(time);
  if (time < 9.2) return frameTwoLayers(time);
  if (time < 11) return frameTwist(time);
  if (time < 18.2) return frameMethods(time);
  return frameEnd(time);
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: "utf8", ...options });
  if (result.status !== 0) {
    throw new Error(`${command} failed\n${result.stderr || result.stdout}`);
  }
  return result;
}

requireCommand("rsvg-convert");
requireCommand("ffmpeg");

mkdirSync(dirname(outputPath), { recursive: true });
const frameDir = mkdtempSync(join(tmpdir(), "gloss-launch-"));

try {
  for (let frame = 0; frame < frameCount; frame += 1) {
    const time = frame / fps;
    const framePath = join(frameDir, `frame-${String(frame).padStart(4, "0")}.png`);
    run("rsvg-convert", ["--width", String(width), "--height", String(height), "--output", framePath], {
      input: renderFrame(time),
    });
    if (frame % 90 === 0) process.stdout.write(`Rendered ${frame}/${frameCount} frames\n`);
  }

  const posterFrame = join(frameDir, `frame-${String(frameCount - 1).padStart(4, "0")}.png`);
  copyFileSync(posterFrame, posterPath);

  run("ffmpeg", [
    "-y",
    "-loglevel", "error",
    "-framerate", String(fps),
    "-i", join(frameDir, "frame-%04d.png"),
    "-t", String(duration),
    "-c:v", "libx264",
    "-preset", "slow",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    "-metadata", `title=Gloss — ${evidence.product_retronym}`,
    "-metadata", `comment=Rendered from ${evidence.evidence_id}`,
    "-an",
    outputPath,
  ]);

  if (!existsSync(outputPath)) throw new Error("Video renderer did not create its output");
  process.stdout.write(`Created ${outputPath}\nCreated ${posterPath}\n`);
} finally {
  rmSync(frameDir, { recursive: true, force: true });
}
