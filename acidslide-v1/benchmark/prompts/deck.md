# AcidSlide v1 — Deck-Level Prompt

This prompt is the primary deck-wide requirements contract. It is authored independently of the reference deck; reference PNGs are supplementary guidance only. Build a new `.pptx` from these instructions in the pinned LibreOffice environment.

## Critical Rules (Read Before Starting)

### Tool
- **Author from a new document in the pinned LibreOffice Impress environment.** Save directly as `.pptx`; do not begin from or round-trip an existing PowerPoint-authored file.
- The official render is the PNG export produced by the pinned LibreOffice environment. Inspect that export while authoring and correct any text wrapping, chart formatting, spacing, or field issues there.
- Use only standards-based constructs that LibreOffice writes as native OOXML. Do not use Microsoft PowerPoint, Google Slides, or Keynote in the canonical authoring workflow.
- The deck must be reproducible from these prompts, bundled assets, and bundled fonts without consulting the gold deck.

### Slide Size
- **16:9 widescreen** (33.867 cm × 19.05 cm / 13.333" × 7.5")
- Set this before creating any slides: Slide → Slide Properties → Width/Height

### Fonts — ONLY USE THESE
You may ONLY use fonts from this exact list. Do not use ANY other fonts, not even system defaults.

| Font | Use For | Notes |
|------|---------|-------|
| **Liberation Sans** | Body text, labels, UI elements | Metric-compatible with Arial |
| **Liberation Serif** | Serif body text, formal content | Metric-compatible with Times New Roman |
| **Liberation Mono** | Code, monospaced content | Metric-compatible with Courier New |
| **Carlito** | Headings, titles | Metric-compatible with Calibri |
| **Caladea** | Serif headings | Metric-compatible with Cambria |
| **Noto Sans** | Multilingual content (Latin) | |
| **Noto Sans Arabic** | Arabic text | RTL support |
| **Noto Sans CJK JP** | Japanese text | CJK support; family exposed by the bundled TTC |

Install these exact files from `benchmark/fonts/files/` before authoring. Do not
download or substitute a similarly named font: `benchmark/fonts/manifest.json`
is the authoritative family, package-version, and SHA-256 inventory.

### Images and Assets
- Use an image only when its exact repository path is named by a canonical slide prompt and the corresponding path relative to `benchmark/assets/` appears as `local_path` in `benchmark/assets/manifest.json`.
- Do not infer an image allowance from `DESIGNER_BRIEF.md`, a reference image, or any external source.
- Do not download images from the internet.

### What NOT To Do
- NO SmartArt
- NO animations or transitions
- NO video or audio
- NO speaker notes
- NO comments
- NO hidden slides
- NO vertical East Asian text layout
- NO embedded macros or scripts

---

## Deck-Level Design System

The entire deck must follow a consistent design language:

A more specific canonical slide clause overrides a deck-wide default only for the property it explicitly names. All other deck-wide defaults remain mandatory. This precedence rule applies to typography, color, layout, and local overrides.

### Color Palette
| Role | Color | Hex |
|------|-------|-----|
| Primary | Deep navy | `#1B2A4A` |
| Secondary | Warm coral | `#E8634A` |
| Accent 1 | Bright teal | `#2AACB8` |
| Accent 2 | Gold/amber | `#D4A843` |
| Background (dark slides) | Near-black | `#0F1923` |
| Background (light slides) | Off-white | `#F5F3EE` |
| Text on dark | White | `#FFFFFF` |
| Text on light | Charcoal | `#2D2D2D` |

### Typography Scale
| Element | Font | Size | Weight |
|---------|------|------|--------|
| Slide title | Carlito | 36pt | Bold |
| Subtitle | Carlito | 24pt | Regular |
| Body text | Liberation Sans | 18pt | Regular |
| Small text/labels | Liberation Sans | 14pt | Regular |
| Caption | Liberation Sans | 12pt | Italic |
| Code | Liberation Mono | 14pt | Regular |

### Master Slides and Layouts

**You MUST create the following masters/layouts before building slides.** Some slides specifically test whether AI models correctly use masters rather than copying elements manually.

#### Master: "AcidSlide Master"
- Background: solid `#0F1923`
- Slide number placeholder in bottom-right corner: Liberation Sans 10pt, `#FFFFFF` at 50% opacity
- Thin horizontal line (0.5pt, `#2AACB8`) at y=17.5cm spanning full width
- Company name "ACIDSLIDE" in bottom-left: Liberation Sans 8pt, `#FFFFFF` at 30% opacity

#### Layout 1: "Title Slide"
- Based on AcidSlide Master
- Title placeholder: centered, Carlito 44pt Bold, `#FFFFFF`
- Subtitle placeholder: centered below title, Carlito 24pt, `#E8634A`

#### Layout 2: "Content Slide"
- Based on AcidSlide Master
- Title placeholder: top-left, Carlito 36pt Bold, `#FFFFFF`
- Body placeholder: below title, Liberation Sans 18pt, `#F5F3EE`
- Accent bar: 0.070556cm wide vertical bar on the left edge, `#E8634A`. This equals 4 pixels in the official 1920×1080 export; the physical width is the authoring requirement.

#### Layout 3: "Two-Column"
- Based on AcidSlide Master
- Title placeholder: top, Carlito 36pt Bold, `#FFFFFF`
- Left body placeholder: left half
- Right body placeholder: right half

#### Layout 4: "Blank with Footer"
- Based on AcidSlide Master
- No content placeholders (only the master footer elements)

---
