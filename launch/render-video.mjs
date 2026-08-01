#!/usr/bin/env node

import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, extname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const launchDir = dirname(fileURLToPath(import.meta.url));
const root = resolve(launchDir, "..");
const outputPath = join(root, "site/media/gloss-launch.mp4");
const posterPath = join(root, "site/media/gloss-launch-poster.png");
const exportsDir = join(root, "gloss-v1/benchmark/deck/exports");

const width = 1080;
const height = 1080;
const fps = 30;
const duration = 21;
const frameCount = fps * duration;
const colors = {
  canvas: "#f2efe8",
  paper: "#fffdf8",
  ink: "#111923",
  muted: "#66707b",
  rule: "#c6c2b8",
  orange: "#e45b35",
  orangeSoft: "#f9ded4",
  blue: "#2859d6",
  blueSoft: "#dfe8ff",
  acid: "#c8ff63",
};

function commandExists(command) {
  return spawnSync("sh", ["-c", `command -v ${command}`], { stdio: "ignore" }).status === 0;
}

function requireCommand(command) {
  if (!commandExists(command)) throw new Error(`${command} is required to render the launch video`);
}

function clamp(value, min = 0, max = 1) {
  return Math.min(max, Math.max(min, value));
}

function ease(value) {
  const t = clamp(value);
  return 1 - (1 - t) ** 3;
}

function fadeInOut(t, start, end, edge = 0.35) {
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
    size: 19,
    weight: 700,
    spacing: 1.2,
    ...options,
  });
}

function baseSvg(body, background = colors.canvas) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <rect width="${width}" height="${height}" fill="${background}"/>
    ${body}
  </svg>`;
}

function imageData(path) {
  const mime = extname(path) === ".png" ? "image/png" : "image/jpeg";
  return `data:${mime};base64,${readFileSync(path).toString("base64")}`;
}

const slides = {
  cover: imageData(join(exportsDir, "slide-01.png")),
  composite: imageData(join(exportsDir, "slide-13.png")),
  final: imageData(join(exportsDir, "slide-20.png")),
};

function slideFrame(href, x, y, w, h, options = {}) {
  const { active = false, label = "NATIVE SLIDE", index = "01" } = options;
  const handle = 12;
  const selection = active
    ? `<rect x="${x + w * 0.55}" y="${y + h * 0.17}" width="${w * 0.29}" height="${h * 0.48}" fill="none" stroke="${colors.blue}" stroke-width="4"/>
       ${[
         [x + w * 0.55, y + h * 0.17],
         [x + w * 0.84, y + h * 0.17],
         [x + w * 0.55, y + h * 0.65],
         [x + w * 0.84, y + h * 0.65],
       ].map(([hx, hy]) => `<rect x="${hx - handle / 2}" y="${hy - handle / 2}" width="${handle}" height="${handle}" fill="${colors.paper}" stroke="${colors.blue}" stroke-width="3"/>`).join("")}`
    : "";
  return `
    <g>
      <rect x="${x - 2}" y="${y - 46}" width="${w + 4}" height="${h + 50}" rx="8" fill="${colors.paper}" stroke="${colors.ink}" stroke-width="2"/>
      <circle cx="${x + 20}" cy="${y - 23}" r="5" fill="${colors.orange}"/>
      <circle cx="${x + 38}" cy="${y - 23}" r="5" fill="${colors.rule}"/>
      ${mono(`${index} / ${label}`, x + 58, y - 17, { size: 12, fill: colors.muted })}
      <image href="${href}" x="${x}" y="${y}" width="${w}" height="${h}" preserveAspectRatio="xMidYMid meet"/>
      ${selection}
    </g>`;
}

function frameIntro(t) {
  const p = ease(t / 1.25);
  const opacity = fadeInOut(t, 0, 3.2, 0.3);
  return baseSvg(`
    <g opacity="${opacity}" transform="translate(0 ${30 * (1 - p)})">
      ${mono("GLOSS / AN OPEN ACID TEST", 72, 108, { fill: colors.orange })}
      ${svgText("Make the deck.", 72, 430, { size: 116, weight: 780 })}
      ${svgText("Not a screenshot.", 72, 552, { size: 116, weight: 780, fill: colors.blue })}
      <rect x="74" y="608" width="${782 * p}" height="14" fill="${colors.orange}"/>
      ${svgText("One deliberately complicated presentation", 76, 744, { size: 50, weight: 650 })}
      ${svgText("that AI struggles to make natively.", 76, 807, { size: 50, weight: 650 })}
      ${mono("POWERPOINT · GOOGLE SLIDES · KEYNOTE", 76, 974, { fill: colors.muted })}
    </g>
  `);
}

function frameDeck(t) {
  const local = t - 3.2;
  const opacity = fadeInOut(t, 3.2, 8, 0.3);
  const p = ease(local / 1.1);
  return baseSvg(`
    <g opacity="${opacity}">
      ${mono("THE CHALLENGE IS THE PRESENTATION", 64, 78, { fill: colors.orange })}
      ${svgText("20 slides.", 64, 182, { size: 78, weight: 780 })}
      ${svgText("No easy outs.", 64, 260, { size: 78, weight: 780, fill: colors.blue })}
      <g transform="translate(0 ${24 * (1 - p)})">
        ${slideFrame(slides.cover, 64, 360, 500, 281, { index: "01" })}
        ${slideFrame(slides.composite, 518, 558, 500, 281, { index: "13", label: "COMPOSITE STRESS" })}
        ${slideFrame(slides.final, 64, 754, 500, 281, { index: "20", label: "FINAL TORTURE" })}
      </g>
      ${mono("CHARTS · TABLES · FIELDS · MASTERS · RTL · GROUPS", 1014, 1025, { anchor: "end", size: 15, fill: colors.muted })}
    </g>
  `);
}

function frameNative(t) {
  const local = t - 8;
  const opacity = fadeInOut(t, 8, 12.4, 0.3);
  const p = ease(local / 1.4);
  const list = ["LIVE CHART", "NATIVE TABLE", "EDITABLE TEXT", "REAL CONNECTIONS"];
  return baseSvg(`
    <g opacity="${opacity}">
      ${mono("LOOK UNDER THE PIXELS", 64, 76, { fill: colors.orange })}
      ${slideFrame(slides.composite, 64, 182, 678, 381, { active: true, index: "13", label: "COMPOSITE STRESS" })}
      <g transform="translate(${18 * (1 - p)} 0)">
        ${svgText("Everything", 64, 700, { size: 86, weight: 780 })}
        ${svgText("stays editable.", 64, 786, { size: 86, weight: 780, fill: colors.blue })}
        ${list.map((item, index) => `${mono(`0${index + 1}`, 70 + (index % 2) * 465, 890 + Math.floor(index / 2) * 76, { fill: colors.orange })}${svgText(item, 120 + (index % 2) * 465, 891 + Math.floor(index / 2) * 76, { size: 24, weight: 720 })}`).join("")}
      </g>
    </g>
  `);
}

function frameCheck(t) {
  const local = t - 12.4;
  const opacity = fadeInOut(t, 12.4, 15.8, 0.25);
  const cursor = clamp(local / 0.7);
  const findings = clamp((local - 0.9) / 0.7);
  return baseSvg(`
    <g opacity="${opacity}">
      ${mono("THE CHECKER IS THE SUPPORT LAYER", 70, 92, { fill: colors.orange })}
      ${svgText("Move two things.", 70, 226, { size: 86, weight: 780 })}
      ${svgText("See two things.", 70, 312, { size: 86, weight: 780, fill: colors.blue })}
      <rect x="70" y="402" width="940" height="456" rx="12" fill="${colors.ink}"/>
      <circle cx="102" cy="438" r="7" fill="${colors.orange}"/>
      <circle cx="128" cy="438" r="7" fill="#657080"/>
      ${mono("$ gloss check edited.pptx", 110, 536, { size: 24, fill: colors.paper, opacity: cursor })}
      <g opacity="${findings}">
        ${mono("2 native objects changed:", 110, 632, { size: 23, fill: colors.acid })}
        ${mono("Slide 02 · Agenda · position", 110, 708, { size: 21, fill: "#cdd4df" })}
        ${mono("Slide 12 · Document Fields · position", 110, 766, { size: 21, fill: "#cdd4df" })}
      </g>
      ${mono("MEASUREMENT MADE EASY · THE DECK REMAINS THE POINT", 70, 978, { fill: colors.muted, size: 16 })}
    </g>
  `);
}

function frameAcid(t) {
  const local = t - 15.8;
  const opacity = fadeInOut(t, 15.8, 18.4, 0.25);
  const p = ease(local / 1.1);
  return baseSvg(`
    <g opacity="${opacity}">
      ${mono("REMEMBER ACID?", 74, 96, { fill: colors.orange })}
      ${svgText("One hostile", 74, 342, { size: 112, weight: 780 })}
      ${svgText("public artifact.", 74, 454, { size: 112, weight: 780, fill: colors.blue })}
      <rect x="76" y="510" width="${750 * p}" height="14" fill="${colors.orange}"/>
      ${svgText("Visible failures.", 76, 640, { size: 64, weight: 720 })}
      ${svgText("A community that fixes them.", 76, 714, { size: 64, weight: 720 })}
      ${mono("ACID1", 76, 918, { fill: colors.muted })}
      ${mono("ACID2", 288, 918, { fill: colors.muted })}
      ${mono("ACID3", 500, 918, { fill: colors.muted })}
      ${mono("GLOSS", 848, 918, { fill: colors.orange })}
      <line x1="76" y1="946" x2="1004" y2="946" stroke="${colors.rule}" stroke-width="2"/>
    </g>
  `);
}

function frameEnd(t) {
  const local = t - 18.4;
  const p = ease(local / 1.1);
  const opacity = clamp(local / 0.25);
  return baseSvg(`
    <g opacity="${opacity}" transform="translate(0 ${22 * (1 - p)})">
      ${mono("ACID FOR PRESENTATION DECKS MADE BY AI", 74, 94, { fill: colors.acid })}
      ${svgText("Gloss", 70, 380, { size: 232, weight: 790, fill: colors.paper })}
      <rect x="76" y="430" width="${590 * p}" height="13" fill="${colors.orange}"/>
      ${svgText("Generative Layout &", 76, 548, { size: 49, weight: 690, fill: "#d4dae3" })}
      ${svgText("Object Structure Standard", 76, 608, { size: 49, weight: 690, fill: "#d4dae3" })}
      <line x1="76" y1="694" x2="1004" y2="694" stroke="#4b5361" stroke-width="2"/>
      ${svgText("Download the deck.", 76, 782, { size: 51, weight: 760, fill: colors.paper })}
      ${svgText("Copy the prompt. Build it with us.", 76, 845, { size: 51, weight: 760, fill: colors.paper })}
      ${svgText("gloss.tools", 76, 988, { size: 72, weight: 760, fill: colors.paper })}
      ${mono("GITHUB.COM/ARONCHICK/GLOSS  ↗", 1004, 982, { fill: colors.orange, anchor: "end", size: 16 })}
    </g>
  `, colors.ink);
}

function renderFrame(time) {
  if (time < 3.2) return frameIntro(time);
  if (time < 8) return frameDeck(time);
  if (time < 12.4) return frameNative(time);
  if (time < 15.8) return frameCheck(time);
  if (time < 18.4) return frameAcid(time);
  return frameEnd(time);
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: "utf8", ...options });
  if (result.status !== 0) throw new Error(`${command} failed\n${result.stderr || result.stdout}`);
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
    "-metadata", "title=Gloss — Make the deck, not a screenshot",
    "-metadata", "comment=Rendered from the public Gloss v1 presentation challenge",
    "-an",
    outputPath,
  ]);

  if (!existsSync(outputPath)) throw new Error("Video renderer did not create its output");
  process.stdout.write(`Created ${outputPath}\nCreated ${posterPath}\n`);
} finally {
  rmSync(frameDir, { recursive: true, force: true });
}
