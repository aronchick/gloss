#!/usr/bin/env node

import { createHash } from "node:crypto";
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const launchDir = dirname(fileURLToPath(import.meta.url));
const root = resolve(launchDir, "..");
const site = join(root, "site");
const evidencePath = join(site, "evidence/preview-v1.json");
const evidence = JSON.parse(readFileSync(evidencePath, "utf8"));
const reportPath = join(root, "acidslide-v1/benchmark/fixtures/mutations/execution-report-v1.json");
const indexPath = join(root, "acidslide-v1/benchmark/fixtures/mutations/fixture-index-v1.json");
const expectationsPath = join(root, "acidslide-v1/benchmark/fixtures/mutations/mutation-expectations-v1.json");
const requirementsPath = join(root, "acidslide-v1/benchmark/requirements/prompt-requirements.json");
const report = JSON.parse(readFileSync(reportPath, "utf8"));
const index = JSON.parse(readFileSync(indexPath, "utf8"));
const requirements = JSON.parse(readFileSync(requirementsPath, "utf8"));
const html = readFileSync(join(site, "index.html"), "utf8");
const headers = readFileSync(join(site, "_headers"), "utf8");
const robots = readFileSync(join(site, "robots.txt"), "utf8");
const sitemap = readFileSync(join(site, "sitemap.xml"), "utf8");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

const methodCounts = Object.fromEntries(
  Object.entries(index.entries.reduce((counts, entry) => {
    counts[entry.verification_method] = (counts[entry.verification_method] || 0) + 1;
    return counts;
  }, {})),
);
const positivePassed = report.results.filter((result) => result.positive_passed).length;
const mutantsDetected = report.results.filter((result) => result.mutant_killed).length;
const visual = methodCounts.visual_ssim;
const insideFile = index.entries.length - visual;
const requirementCounts = requirements.requirements.reduce((counts, requirement) => {
  counts[requirement.scope] = (counts[requirement.scope] || 0) + 1;
  return counts;
}, {});

assert(evidence.status === "technical_preview", "Launch evidence must remain labeled technical_preview");
assert(evidence.operator_evidence.release_evidence_claimed === 0, "Preview must not claim release evidence");
assert(evidence.candidate_checks.total === index.entries.length, "Candidate-check count drifted from fixture index");
assert(evidence.candidate_checks.visual_render === visual, "Visual-check count drifted from fixture index");
assert(evidence.candidate_checks.inside_file === insideFile, "Inside-file count drifted from fixture index");
assert(evidence.prompt_requirements.total === requirements.requirements.length, "Prompt-requirement total drifted from oracle");
assert(evidence.prompt_requirements.deck === requirementCounts.deck, "Deck requirement count drifted from oracle");
assert(evidence.prompt_requirements.slide === requirementCounts.slide, "Slide requirement count drifted from oracle");
assert(evidence.operator_evidence.positive_controls_passed === positivePassed, "Positive-control count drifted from execution report");
assert(evidence.operator_evidence.single_fault_mutations_detected === mutantsDetected, "Mutation count drifted from execution report");

for (const method of evidence.verification_methods) {
  assert(method.count === methodCounts[method.id], `Verification method ${method.id} drifted from fixture index`);
  const htmlLabel = method.public_label.replaceAll("&", "&amp;");
  assert(html.includes(`<span>${htmlLabel}</span>`) && html.includes(`<b>${method.count}</b>`), `Homepage method count is missing for ${method.id}`);
}

const sourcePaths = new Map([
  ["acidslide-v1/benchmark/fixtures/mutations/execution-report-v1.json", reportPath],
  ["acidslide-v1/benchmark/fixtures/mutations/fixture-index-v1.json", indexPath],
  ["acidslide-v1/benchmark/fixtures/mutations/mutation-expectations-v1.json", expectationsPath],
  ["acidslide-v1/benchmark/requirements/prompt-requirements.json", requirementsPath],
]);
for (const source of evidence.sources) {
  const sourcePath = sourcePaths.get(source.path);
  assert(sourcePath, `Unknown evidence source ${source.path}`);
  assert(sha256(sourcePath) === source.sha256, `SHA-256 drifted for ${source.path}`);
}

const requiredCopy = [
  "A screenshot is not a",
  "Open technical preview",
  "0 official model results",
  "The repository is the product",
  "Working harness. Unfrozen benchmark.",
];
for (const copy of requiredCopy) assert(html.includes(copy), `Homepage is missing required copy: ${copy}`);
assert(!/official leaderboard[^<]{0,80}(live|launched|ready)/i.test(html), "Homepage overclaims official leaderboard readiness");
assert(html.includes("https://github.com/aronchick/gloss"), "Homepage must lead to GitHub");
assert(html.includes('<link rel="canonical" href="https://gloss.tools/">'), "Homepage canonical URL is missing");
assert(html.includes('"codeRepository": "https://github.com/aronchick/gloss"'), "Homepage structured data must lead to GitHub");
assert(robots.includes("Allow: /") && robots.includes("Sitemap: https://gloss.tools/sitemap.xml"), "robots.txt must expose the public site map");
assert(sitemap.includes("<loc>https://gloss.tools/</loc>"), "sitemap.xml must contain the production homepage");
for (const header of [
  "X-Content-Type-Options: nosniff",
  "Referrer-Policy: strict-origin-when-cross-origin",
  "Permissions-Policy: camera=(), microphone=(), geolocation=()",
  "X-Frame-Options: DENY",
]) {
  assert(headers.includes(header), `Cloudflare Pages header is missing: ${header}`);
}

const localAssetPattern = /(?:href|src)="\/(?!\/)([^"?#]*)/g;
for (const match of html.matchAll(localAssetPattern)) {
  if (!match[1]) continue;
  const assetPath = join(site, match[1]);
  assert(existsSync(assetPath), `Homepage references missing local asset /${match[1]}`);
}

const videoPath = join(site, "media/gloss-launch.mp4");
const posterPath = join(site, "media/gloss-launch-poster.png");
assert(statSync(videoPath).size > 100_000, "Launch video is missing or unexpectedly small");
assert(statSync(posterPath).size > 20_000, "Launch poster is missing or unexpectedly small");

const probe = spawnSync("ffprobe", [
  "-v", "error",
  "-show_entries", "stream=codec_type,width,height,avg_frame_rate:format=duration",
  "-of", "json",
  videoPath,
], { encoding: "utf8" });
assert(probe.status === 0, `ffprobe is required to verify launch media: ${probe.stderr}`);
const metadata = JSON.parse(probe.stdout);
const video = metadata.streams.find((stream) => stream.codec_type === "video");
const audio = metadata.streams.find((stream) => stream.codec_type === "audio");
assert(video?.width === 1080 && video?.height === 1080, "Launch video must be 1080x1080");
assert(video?.avg_frame_rate === "30/1", "Launch video must be 30 fps");
assert(Math.abs(Number(metadata.format.duration) - 21) < 0.05, "Launch video must be 21 seconds");
assert(!audio, "Launch video must be silent and contain no audio stream");

process.stdout.write(`Launch verification: PASS\n- evidence: ${evidence.evidence_id}\n- candidate checks: ${index.entries.length}\n- positive controls: ${positivePassed}/${report.results.length}\n- mutants detected: ${mutantsDetected}/${report.results.length}\n- site assets: present\n- video: 1080x1080, 30 fps, 21 seconds, silent\n`);
