# Gloss v1 — Canonical Deck Authoring Brief

## What This Document Is

You are building the **canonical Gloss v1 reference deck**, a public benchmark target for presentation-generation systems. Every submitted deck is compared with this reference under the pinned LibreOffice renderer and by OOXML inspection.

This prompt suite is the primary requirements contract and was authored before the reference deck. Reference images are supplementary visual guidance only: explicit prompt requirements take precedence. Follow this brief precisely and do not infer hidden constraints from any reference export.

---

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

#### Master: "Gloss Master"
- Background: solid `#0F1923`
- Slide number placeholder in bottom-right corner: Liberation Sans 10pt, `#FFFFFF` at 50% opacity
- Thin horizontal line (0.5pt, `#2AACB8`) at y=17.5cm spanning full width
- Company name "GLOSS" in bottom-left: Liberation Sans 8pt, `#FFFFFF` at 30% opacity

#### Layout 1: "Title Slide"
- Based on Gloss Master
- Title placeholder: centered, Carlito 44pt Bold, `#FFFFFF`
- Subtitle placeholder: centered below title, Carlito 24pt, `#E8634A`

#### Layout 2: "Content Slide"
- Based on Gloss Master
- Title placeholder: top-left, Carlito 36pt Bold, `#FFFFFF`
- Body placeholder: below title, Liberation Sans 18pt, `#F5F3EE`
- Accent bar: 0.070556cm wide vertical bar on the left edge, `#E8634A`. This equals 4 pixels in the official 1920×1080 export; the physical width is the authoring requirement.

#### Layout 3: "Two-Column"
- Based on Gloss Master
- Title placeholder: top, Carlito 36pt Bold, `#FFFFFF`
- Left body placeholder: left half
- Right body placeholder: right half

#### Layout 4: "Blank with Footer"
- Based on Gloss Master
- No content placeholders (only the master footer elements)

---

## Slide-by-Slide Instructions

### SLIDE 1: Cover / Title Stress Test
**Layout:** "Title Slide" (from master)
**Tier:** Level 1

**What to build:**

1. Use the "Title Slide" layout — the title and subtitle MUST come from the layout placeholders, not freestanding text boxes.

2. **Title text** (in the title placeholder):
   ```
   Gloss v1
   ```

3. **Subtitle text** (in the subtitle placeholder):
   ```
   Benchmark for Slide Generation Fidelity
   ```

4. **Hero image**: Place `benchmark/assets/mirrored/hero-abstract.png` at x=18.867cm, y=2cm in a 15cm-wide frame whose height is proportional to the uncropped image. Keep that frame fixed, then crop 20% from the source image's left edge. The frame's right edge is exactly the slide's right edge.
   - The image should overlap with decorative shapes (see below)

5. **Decorative shapes** (3 overlapping rounded rectangles):
   - Rectangle A: 8cm × 8cm, position (14cm, 4cm), fill `#2AACB8` at 40% opacity, corner radius 0.5cm, NO outline
   - Rectangle B: 6cm × 10cm, position (18cm, 1cm), fill `#E8634A` at 30% opacity, corner radius 0.5cm, NO outline
   - Rectangle C: 10cm × 6cm, position (16cm, 8cm), fill `#D4A843` at 25% opacity, corner radius 0.5cm, NO outline

6. **Z-order** (bottom to top): Master background → Rectangle C → Rectangle A → Hero image → Rectangle B → Title text → Subtitle text

7. **Shadow**: Apply a soft outer shadow to the hero image: color `#000000` at 40% opacity, offset 3mm down and 2mm right, blur 5mm.

8. **Slide number**: must come from the master's slide number placeholder (do NOT type "1" manually).

**Why this slide is hard for AI:**
- Tests placeholder usage (not manual text boxes)
- Tests precise crop rectangle on an image
- Tests z-order with overlapping semi-transparent shapes
- Tests shadow parameters
- Tests master-driven footer/slide number inheritance

---

### SLIDE 2: Dense Agenda with Layout Semantics
**Layout:** "Content Slide" (from master)
**Tier:** Level 1

**What to build:**

1. Use the "Content Slide" layout. Title and body MUST be in the layout placeholders.

2. **Title** (placeholder): `Agenda`

3. **Body** (placeholder) — a bulleted list with specific formatting:
   ```
   • Opening Remarks
     ◦ Welcome and introductions
     ◦ Safety briefing
   • Technical Deep Dive
     ◦ Architecture overview
     ◦ Performance benchmarks
     ◦ Security audit results
   • Breakout Sessions
     ◦ Track A: Infrastructure
     ◦ Track B: Applications
   • Closing & Next Steps
   ```

   - Level 1 bullets (•): Liberation Sans 18pt Bold, `#E8634A`
   - Level 2 bullets (◦): Liberation Sans 14pt Regular, `#F5F3EE`
   - Bullet indent: Level 1 = 0.5cm, Level 2 = 1.5cm
   - Line spacing: 1.2× for Level 1, 1.0× for Level 2
   - Paragraph spacing: 6pt after each Level 1 item

   Use native paragraph-bullet properties. The shown `•` and `◦` characters specify the required bullet glyphs and are not literal characters in the paragraph text runs.

4. **Grouped icon-text rows**: Create three icon-text rows on the right. Each row contains one 1cm teal circle and one time label. Put all six leaf objects directly in one flat group; do not create row subgroups. Align the group's top to the first bullet and bottom to the last bullet. Exact horizontal position and the two intermediate row gaps are intentionally unconstrained and unscored.
   - The three time labels, from top to bottom, are "09:00", "11:30", and "14:00" in Liberation Sans 14pt Bold `#FFFFFF`.
   - Each circle is filled with `#2AACB8`.

**Why this slide is hard for AI:**
- Tests bullet hierarchy (indentation, different bullet characters)
- Tests paragraph-level formatting (spacing, indent)
- Tests object grouping (the time column must be one group)
- Tests placeholder usage for title and body
- Tests alignment precision

---

### SLIDE 3: Native Table Stress Test
**Layout:** "Blank with Footer" (from master)
**Tier:** Level 1

**What to build:**

1. **Title text box** (freestanding, NOT a placeholder — this slide uses Layout 4 which has no content placeholders):
   - Text: `Performance Metrics`
   - Font: Carlito 36pt Bold, `#FFFFFF`
   - Position: x=1.5cm, y=0.8cm

2. **Native table** — this MUST be a real LibreOffice Impress table, not shapes pretending to be a table:
   - Position: x=1.5cm, y=3cm
   - Size: 30cm × 12cm
   - Rows: 7 (1 header + 6 data)
   - Columns: 5

   | Metric | Q1 2024 | Q2 2024 | Q3 2024 | Target |
   |--------|---------|---------|---------|--------|
   | Latency (p50) | 12ms | 11ms | 9ms | ≤10ms |
   | Latency (p99) | 89ms | 72ms | 58ms | ≤75ms |
   | Throughput | 1,200 rps | 1,450 rps | 1,890 rps | ≥2,000 rps |
   | Error Rate | 0.12% | 0.08% | 0.04% | ≤0.05% |
   | Uptime | 99.91% | 99.95% | 99.98% | ≥99.95% |
   | Cache Hit | 72% | 78% | 84% | ≥80% |

   **Table styling:**
   - Header row: background `#1B2A4A`, text Carlito 14pt Bold `#FFFFFF`, centered
   - Data rows: alternating `#0F1923` and `#161F2E`
   - Data text: Liberation Sans 14pt, `#F5F3EE`, left-aligned for "Metric", centered for all others
   - Cell padding: 0.3cm on all sides
   - Borders: 0.5pt `#2AACB8` between all cells, 2pt `#2AACB8` below header row
   - Q3 column: color each Q3 value `#2AACB8` when it meets the Target-column threshold and `#E8634A` when it misses that threshold.
     - Q3: Latency p50 (9 ≤ 10 ✓), p99 (58 ≤ 75 ✓), Throughput (1890 misses 2000 ✗), Error (0.04 ≤ 0.05 ✓), Uptime (99.98 ≥ 99.95 ✓), Cache (84 ≥ 80 ✓)

3. **Annotation callout** — a rounded rectangle with text, positioned next to the table:
   - Position: x=24cm, y=15.5cm
   - Size: 8cm × 2.5cm
   - Fill: `#E8634A`
   - Corner radius: 0.3cm
   - Text: "Throughput target\nmissed by 5.5%" in Liberation Sans 12pt Bold `#FFFFFF`, centered
   - A thin line (1pt, `#E8634A`) connecting the callout to the Q3 Throughput cell; connector routing is otherwise unconstrained.

4. **Paragraph indent**: the Metric-column paragraphs must use a 0.5cm left paragraph indent in addition to cell padding. No tab character or tab-stop property is required.

**Why this slide is hard for AI:**
- Tests native table creation (not shapes)
- Tests cell-level formatting (conditional colors)
- Tests table borders (mixed weights)
- Tests tab stops and paragraph indentation inside table cells
- Tests annotation positioning relative to table cells

---

### SLIDE 4: Native Chart Stress Test
**Layout:** "Content Slide" (from master)
**Tier:** Level 1

**What to build:**

1. **Title** (placeholder): `Revenue Growth`

2. **Native chart** — MUST be a real LibreOffice Impress chart, not shapes/images:
   - Chart type: **Clustered bar chart** (horizontal bars)
   - Position: x=1.5cm, y=3cm
   - Size: 20cm × 14cm

   **Chart data:**

   | Region | 2023 Revenue ($M) | 2024 Revenue ($M) |
   |--------|-------------------|--------------------|
   | North America | 42.3 | 51.8 |
   | Europe | 28.7 | 35.2 |
   | Asia Pacific | 19.4 | 31.6 |
   | Latin America | 8.1 | 12.4 |
   | Middle East & Africa | 3.9 | 7.2 |

   **Chart formatting:**
   - 2023 bars: `#1B2A4A` (navy)
   - 2024 bars: `#E8634A` (coral)
   - Chart title: "Annual Revenue by Region" in Carlito 16pt Bold
   - X-axis value labels: Liberation Sans 11pt, `#2D2D2D`, format `$0M`.
   - Y-axis category labels: Liberation Sans 12pt, `#2D2D2D`.
   - Legend: bottom of chart, Liberation Sans 11pt
   - Gridlines: vertical major-value gridlines only, `#E0E0E0` 0.5pt.
   - No chart border
   - Background: transparent (slide background shows through)

3. **Callout shapes** — two overlaid callout annotations:

   - Callout 1: positioned over the "Asia Pacific 2024" bar
     - Rounded rectangle, 5cm × 2cm
     - Fill: `#2AACB8`
     - Text: "+62.9% YoY" in Liberation Sans 14pt Bold `#FFFFFF`
     - Arrow connector pointing from callout to the bar

   - Callout 2: positioned over the "Middle East & Africa 2024" bar
     - Rounded rectangle, 5cm × 2cm
     - Fill: `#D4A843`
     - Text: "+84.6% YoY" in Liberation Sans 14pt Bold `#FFFFFF`
     - Arrow connector pointing from callout to the bar

4. **Supporting text block** to the right of the chart:
   - Position: x=23cm, y=4cm
   - Width: 9cm
   - Text (Liberation Sans 14pt, `#F5F3EE`):
     ```
     Key Takeaways:
     
     ▸ Total revenue up 38.2% YoY
     ▸ APAC fastest-growing region
     ▸ All regions exceeded targets
     ```

**Why this slide is hard for AI:**
- Tests native chart creation with specific chart type
- Tests chart formatting (colors, labels, gridlines, legend)
- Tests chart data accuracy
- Tests overlay shapes on top of chart
- Tests connector arrows between callouts and chart elements

---

### SLIDE 5: Master Reuse Enforcement
**Layout:** "Content Slide" (from master)
**Tier:** Level 1

**What to build:**

This slide's purpose is to verify that the master/layout is being used correctly, not just visually copied.

1. **Title** (placeholder): `Our Team`

2. **Body content** — three team member cards arranged horizontally:

   Each card is a group containing:
   - A rounded rectangle: 9cm × 13cm, fill `#161F2E`, corner radius 0.3cm, border 1pt `#2AACB8`
   - Circle placeholder for photo: 4cm diameter, centered at top of card, fill `#1B2A4A` with text "Photo" in center (Liberation Sans 12pt `#FFFFFF`) — since we have no actual photos
   - Name: Carlito 18pt Bold `#FFFFFF`, centered
   - Title: Liberation Sans 14pt `#E8634A`, centered
   - Description: Liberation Sans 12pt `#F5F3EE`, centered, max 3 lines

   **Card 1:**
   - Name: "Sarah Chen"
   - Title: "Chief Architect"
   - Description: "15 years building distributed systems at scale"

   **Card 2:**
   - Name: "Marcus Rivera"
   - Title: "Head of Design"
   - Description: "Formerly at Apple, obsessed with pixel-perfect interfaces"

   **Card 3:**
   - Name: "Yuki Tanaka"
   - Title: "ML Engineering Lead"
   - Description: "PhD in NLP, built the model serving infrastructure"

   Cards positioned at x=1.5cm, x=12cm, x=22.5cm — evenly spaced across the slide.

3. **Critical requirement**: The bottom footer line, "GLOSS" text, and slide number MUST come from the master. Do NOT manually add these elements on this slide. The whole point of this slide is to test that the master is correctly inherited.

4. **The accent bar** on the left edge must also come from the "Content Slide" layout, not a manually placed shape.

**Why this slide is hard for AI:**
- Tests that repeated elements (footer, line, text, slide number) come from master inheritance
- Tests grouped objects (each card is a group)
- Tests precise horizontal distribution of equal-sized elements
- Tests placeholder text formatting within groups

---

### SLIDE 6: Multilingual Editorial
**Layout:** "Blank with Footer" (from master)
**Tier:** Level 2

**What to build:**

1. **Three text columns** side by side:

   **Column 1 — English** (left third):
   - Title: "Global Perspectives" in Carlito 24pt Bold `#FFFFFF`
   - Body (Liberation Sans 14pt `#F5F3EE`, left-aligned):
     ```
     The rapid advancement of language models
     has transformed how organizations approach
     document generation. From financial reports
     to marketing materials, AI-driven content
     creation is reshaping every industry.
     ```

   **Column 2 — Arabic RTL** (center third):
   - Title: "وجهات نظر عالمية" in Noto Sans Arabic 24pt Bold `#FFFFFF`
   - Body (Noto Sans Arabic 14pt `#F5F3EE`, **RIGHT-to-left aligned**):
     ```
     لقد أدى التقدم السريع في نماذج اللغة إلى تحويل
     كيفية تعامل المؤسسات مع إنشاء المستندات. من
     التقارير المالية إلى المواد التسويقية، يعيد إنشاء
     المحتوى المدعوم بالذكاء الاصطناعي تشكيل كل صناعة.
     ```
   - **CRITICAL**: This column must be set to RTL paragraph direction. The text must flow right-to-left. This is NOT just right-alignment — the paragraph direction property must be set to RTL.

   **Column 3 — Japanese** (right third):
   - Title: "グローバルな視点" in Noto Sans CJK JP 24pt Bold `#FFFFFF`
   - Body (Noto Sans CJK JP 14pt `#F5F3EE`, left-aligned):
     ```
     言語モデルの急速な進歩により、組織がドキュメント生成に
     取り組む方法が変革されました。財務報告からマーケティング
     資料まで、AI主導のコンテンツ作成はあらゆる産業を
     再形成しています。
     ```

2. **Decorative separator lines** between columns:
   - Vertical lines at x=11.2cm and x=22.5cm
   - Height: from y=3cm to y=16cm
   - Style: 1pt, `#2AACB8`, 50% opacity

3. **Callout box** overlapping the Arabic and Japanese columns:
   - Position: x=15cm, y=13cm
   - Size: 12cm × 4cm
   - Fill: `#E8634A` at 90% opacity
   - Text: "AI-generated slides must handle RTL text,\nCJK line breaking, and mixed scripts correctly."
   - Font: Liberation Sans 13pt Bold `#FFFFFF`, centered
   - Corner radius: 0.3cm
   - This callout should overlap both the Arabic and Japanese columns

**Why this slide is hard for AI:**
- Tests correct RTL paragraph direction (not just alignment)
- Tests CJK text rendering and line breaking
- Tests correct font assignment per script
- Tests overlap between callout and text columns
- Tests Unicode text preservation (exact characters must match)

---

### SLIDE 7: Image Crop and Mask
**Layout:** "Blank with Footer"
**Tier:** Level 2

**What to build:**

1. **Three images** from the asset manifest, each cropped differently:

   - **Image A**: `benchmark/assets/mirrored/cityscape.png`
     - Size on slide: 10cm × 8cm, position (1.5cm, 2cm)
     - Crop: remove top 15% and bottom 10% of original image
     - No shape mask

   - **Image B**: `benchmark/assets/mirrored/cityscape.png` (same image, different crop)
     - Size on slide: 8cm × 8cm, position (13cm, 2cm)
     - Crop: remove left 30% of original image
     - Apply **circle crop mask** (crop to ellipse shape)

   - **Image C**: `benchmark/assets/mirrored/texture-pattern.png`
     - Size on slide: 10cm × 8cm, position (22.5cm, 2cm)
     - Crop: remove right 25% of original image
     - Apply **rounded rectangle crop mask** with 1cm corner radius

2. **Caption text boxes** below each image:
   - "Full panorama crop" / "Circle-masked detail" / "Rounded corner crop"
   - Liberation Sans 12pt Italic `#F5F3EE`, centered under each image

3. **Overlapping layer test** — place a semi-transparent rectangle OVER Image B:
   - Size: 6cm × 6cm
   - Position: centered on Image B
   - Fill: `#1B2A4A` at 50% opacity
   - Text: "PREVIEW" in Carlito 24pt Bold `#FFFFFF`, centered
   - This rectangle must be ABOVE Image B in z-order

4. **Title**: "Image Handling" in Carlito 36pt Bold `#FFFFFF` at position (1.5cm, 0.5cm)

**Why this slide is hard for AI:**
- Tests different crop rectangles on the same image
- Tests crop-to-shape (circle, rounded rectangle)
- Tests z-order with semi-transparent overlay on an image
- Tests that images come from the approved asset manifest (hash verification)

---

### SLIDE 8: Overlap, Shadow, and Transparency
**Layout:** "Blank with Footer"
**Tier:** Level 2

**What to build:**

1. **Five overlapping "card" shapes** arranged in a cascading stack:

   All cards are rounded rectangles, 12cm × 8cm, corner radius 0.5cm.

   | Card | Position | Fill | Opacity | Shadow |
   |------|----------|------|---------|--------|
   | Card 1 (bottom) | (4cm, 6cm) | `#1B2A4A` | 100% | Yes |
   | Card 2 | (7cm, 5cm) | `#2AACB8` | 85% | Yes |
   | Card 3 | (10cm, 4cm) | `#E8634A` | 70% | Yes |
   | Card 4 | (13cm, 3cm) | `#D4A843` | 55% | Yes |
   | Card 5 (top) | (16cm, 2cm) | `#FFFFFF` | 90% | Yes |

   **Shadow on all cards**: outer shadow, `#000000` at 30% opacity, offset 2mm down and 1mm right, blur 4mm.

   Each card contains centered text:
   - Card 1: "Layer 1" in Liberation Sans 20pt Bold `#FFFFFF`
   - Card 2: "Layer 2" in Liberation Sans 20pt Bold `#FFFFFF`
   - Card 3: "Layer 3" in Liberation Sans 20pt Bold `#FFFFFF`
   - Card 4: "Layer 4" in Liberation Sans 20pt Bold `#1B2A4A`
   - Card 5: "Layer 5" in Liberation Sans 20pt Bold `#1B2A4A`

2. **Z-order** MUST be exactly as listed: Card 1 at bottom, Card 5 on top.

3. **Group test**: Cards 1 and 2 should be grouped together. Cards 3, 4, and 5 should be grouped together. The two groups should NOT be grouped with each other.

4. **Gradient fill shape**: a rectangle at the bottom of the slide (y=15cm, full width, 3cm tall) with a linear gradient from `#0F1923` (left) to `#2AACB8` (right).

5. **Title**: "Depth & Layering" — Carlito 36pt Bold `#FFFFFF`, position (1.5cm, 0.5cm)

**Why this slide is hard for AI:**
- Tests precise z-order with 5 overlapping shapes
- Tests transparency at different levels
- Tests shadow parameters on every card
- Tests selective grouping (not all grouped, specific subsets)
- Tests gradient fill

---

### SLIDE 9: Dense Text Overflow
**Layout:** "Content Slide"
**Tier:** Level 2

**What to build:**

1. **Title** (placeholder): `API Reference`

2. **Two narrow text columns** (each 14cm × 14cm, side by side):

   **Left column** — text box with NO auto-fit (text should clip if it overflows):
   - AutoFit: OFF (resize shape to fit text: OFF, shrink text on overflow: OFF)
   - Text (Liberation Mono 11pt, `#F5F3EE`, left-aligned):
     ```
     GET /api/v1/submissions
     Authorization: Bearer YOUR_TOKEN_HERE
     Content-Type: application/json
     
     Query Parameters:
       model_id    string  required  Filter by model
       tier        integer optional  1, 2, or 3
       status      string  optional  queued|grading|completed
       limit       integer optional  Default: 20, max: 100
       offset      integer optional  Default: 0
     
     Response 200:
     (
       "submissions": [
         (
           "id": "sub_abc123",
           "model_id": "gpt-4o",
           "tier": 3,
           "status": "completed",
           "fidelity_score": 0.847,
           "created_at": "2025-01-15T10:30:00Z"
         )
       ],
       "total": 142,
       "has_more": true
     )
     ```

   Authoring instruction; do not place this note on the slide. In the left column's slide text, replace the six JSON-structural parentheses shown in the fenced example with `{` and `}`. Preserve all other characters.

   **Right column** — text box WITH auto-shrink enabled:
   - AutoFit: Shrink text on overflow = ON
   - Same text content as left column but with this additional block appended:
     ```
     
     Error Responses:
       401 Unauthorized - Invalid or expired token
       403 Forbidden - Rate limit exceeded
       404 Not Found - Submission not found
       422 Unprocessable - Invalid parameters
       500 Internal Server Error - Contact support
     
     Rate Limits:
       Free tier: 10 req/min, 100 req/hour
       Pro tier:  60 req/min, 1000 req/hour
       Enterprise: Custom
     ```

3. **Column labels** above each:
   - "Fixed Size (clips)" over left column — Liberation Sans 11pt Bold `#E8634A`
   - "Auto-Shrink (fits)" over right column — Liberation Sans 11pt Bold `#2AACB8`

4. **Line spacing**: exactly 1.15× throughout both columns.

**Why this slide is hard for AI:**
- Tests autofit behavior (one column clips, one shrinks)
- Tests monospaced text with exact indentation
- Tests dense text layout with no autofit tricks
- Tests line spacing precision
- Tests that text content is preserved exactly (including whitespace)

---

### SLIDE 10: Connector and Alignment Diagram
**Layout:** "Blank with Footer"
**Tier:** Level 2

**What to build:**

1. **Architecture diagram** using ONLY built-in shapes and connectors:

   **Boxes** (all rounded rectangles, 5cm × 3cm, corner radius 0.3cm):

   | Box | Label | Position | Fill |
   |-----|-------|----------|------|
   | Client | "Client App" | (2cm, 3cm) | `#2AACB8` |
   | API Gateway | "API Gateway" | (14cm, 3cm) | `#1B2A4A` |
   | Auth | "Auth Service" | (8cm, 9cm) | `#E8634A` |
   | Grader | "Grader" | (20cm, 9cm) | `#E8634A` |
   | Queue | "Job Queue" | (14cm, 9cm) | `#D4A843` |
   | Storage | "Object Store" | (14cm, 15cm) | `#1B2A4A` |
   | DB | "PostgreSQL" | (6cm, 15cm) | `#1B2A4A` |
   | LB | "Leaderboard" | (22cm, 15cm) | `#2AACB8` |

   No pair of architecture boxes overlaps.

   All box text: Liberation Sans 12pt Bold `#FFFFFF`, centered.

2. **Connectors** — use native connectors (Insert → Connector in LibreOffice), NOT plain lines:
   - Client → API Gateway (straight connector, arrow at end)
   - API Gateway → Auth (elbow connector, arrow at end)
   - API Gateway → Queue (straight connector, arrow at end)
   - Queue → Grader (straight connector, arrow at end)
   - Grader → Storage (straight connector, arrow at end)
   - Storage → DB (straight connector, arrow at end)
   - Storage → LB (straight connector, arrow at end)

   All connectors: 1.5pt, `#F5F3EE`, with arrowhead at destination end.

3. **Labels on connectors** — small text boxes positioned near each connector:
   - Client→Gateway: "HTTPS" (Liberation Sans 10pt `#FFFFFF`)
   - Gateway→Auth: "JWT verify" (Liberation Sans 10pt `#FFFFFF`)
   - Gateway→Queue: "Enqueue" (Liberation Sans 10pt `#FFFFFF`)

4. **Nested grouping**:
   - Group 1: Auth + Queue + Grader boxes (label this group with a thin dashed border, 0.5pt `#FFFFFF` at 30%, and text "Processing Layer" above)
   - Group 2: Storage + DB + LB boxes (label with "Persistence Layer")
   - Group 3: Group 1 + Group 2 (the "Backend" super-group)

5. **Title**: "System Architecture" — Carlito 36pt Bold `#FFFFFF`, position (1.5cm, 0.5cm)

**Why this slide is hard for AI:**
- Tests native connectors (not plain lines)
- Tests nested grouping (groups inside groups)
- Tests precise alignment grid
- Tests connector routing between boxes
- Tests label positioning relative to connectors

---

### SLIDE 11: Theme vs Local Override
**Layout:** "Content Slide"
**Tier:** Level 2

**What to build:**

1. **Title** (placeholder): `Brand Colors`

2. **Six color swatches in two rows of three** — each is a 4cm × 4cm rounded rectangle. Swatches 1–3 are the top row; Swatches 4–6 are the bottom row.

   **Top row — inherited from theme/master** (these must use theme color references, NOT hardcoded hex):
   - Swatch 1: Theme Primary color
   - Swatch 2: Theme Secondary color
   - Swatch 3: Theme Accent 1 color
   
   Below each: text with the role name ("Primary", "Secondary", "Accent 1") in Liberation Sans 12pt `#F5F3EE`

   **Bottom row — locally overridden** (these must use explicit RGB hex, NOT theme references):
   - Swatch 4: `#FF6B35` (explicit override — different from theme)
   - Swatch 5: `#7B2D8E` (explicit override)
   - Swatch 6: `#3D9970` (explicit override)

   Below each: text "Override" in Liberation Sans 12pt, same explicit color as the swatch

3. **The critical test**: if someone changes the theme colors in the master, the top row should change with the theme but the bottom row should stay fixed. This is what the grader checks — theme reference vs. local override in the OOXML.

4. **Explanatory text box** at bottom:
   - "Top row uses theme color references. Bottom row uses explicit RGB values."
   - "Changing the theme will update the top row but not the bottom row."
   - Liberation Sans 13pt `#F5F3EE`

**Why this slide is hard for AI:**
- Tests theme color reference vs. explicit RGB in the OOXML
- Tests that AI understands the semantic difference between inheriting and overriding
- The slide looks similar visually but the XML structure must be different

---

### SLIDE 12: Native Field Slide
**Layout:** "Content Slide"
**Tier:** Level 2

**What to build:**

1. **Title** (placeholder): `Document Fields`

2. **Three field demonstrations** — each in its own text box:

   **Field 1 — Slide Number**:
   - Text box: "Current slide: " followed by an **inserted slide number field** (LibreOffice: Insert → Field → Page Number)
   - Do NOT type the number manually. It MUST be a live field.
   - Liberation Sans 18pt `#FFFFFF`

   **Field 2 — Date/Time**:
   - `Generated: ` followed by a fixed native date/time field with value `2025-01-15T10:30:00Z`, displayed exactly as `2025-01-15 10:30 UTC`; Liberation Sans 18pt `#FFFFFF`.

   **Field 3 — Footer**:
   - The slide footer (from View → Header and Footer) should contain: "Gloss Benchmark v1"
   - This must be enabled via the master's footer placeholder

3. **Explanatory labels** next to each:
   - "← Live slide number field (not static text)"
   - "← Fixed date/time field"
   - "← Footer from master placeholder"
   - Liberation Sans 12pt Italic `#2AACB8`

4. **A static text comparison** — a text box that says "Slide 12" in the same font/size as Field 1, to highlight the difference between static text and a live field.

**Why this slide is hard for AI:**
- Tests native field insertion (not static text that looks like a field)
- Tests date/time field (the grader pins the datetime)
- Tests footer field from master
- The grader verifies field type in OOXML, not just rendered text

---

## Slides 13-20 (Level 3) — Brief Specifications

### SLIDE 13: Composite Stress
Combines: native chart (pie chart, 6 segments), native table (4×3), one approved image, Arabic text annotation, repeated layout elements, dense callout annotations.

## Explicit v1 constraints

- Use the **Blank with Footer** layout and title the slide `Composite Stress` in Carlito 36pt Bold at (1.5cm, 0.5cm).
- Add one native pie chart at (1.5cm, 3cm), size 10cm × 8cm. Use six labeled values: `Structure 28`, `Text 22`, `Visual 18`, `Assets 14`, `Fields 10`, `Other 8`; show percentage labels and no legend.
- Add one native 4-row × 3-column table at (13cm, 3cm), size 9cm × 7cm. Header: `Check`, `Status`, `Weight`. Rows: `Schema | Pass | 3`, `Rendering | Pass | 2`, `Assets | Review | 1`.
- Insert `cityscape.png` at (23cm, 3cm), size 8cm × 6cm, cropping 15% from the left. Use only asset ID `cityscape` from the manifest.
- Add the Arabic annotation `الهيكل والمحتوى والعرض في اختبار واحد` in Noto Sans Arabic 14pt with native RTL direction.
- Add three dense rounded callouts labeled `NATIVE CHART`, `NATIVE TABLE`, and `APPROVED ASSET`; connect each to its target and keep all data labels visible.

### SLIDE 14: RTL-Heavy Comparison
Two-column layout with heavy Arabic text on left (5+ paragraphs with mixed Arabic/English), English summary on right. Bidirectional text within single paragraphs (e.g., "The الذكاء الاصطناعي revolution"). Mirrored alignment: Arabic column is right-aligned, English column is left-aligned.

## Explicit v1 constraints

- Use the **Two-Column** layout with title `RTL Systems Review`.
- The left column contains at least five separate Arabic paragraphs in Noto Sans Arabic 14pt with native RTL paragraph direction. Include these exact phrases: `مراجعة الأنظمة الموزعة`, `دقة العرض`, `سلامة البنية`, `The الذكاء الاصطناعي revolution`, and `الإصدار Gloss v1`.
- The right column contains five English summary paragraphs in Liberation Sans 14pt, beginning with `A structural benchmark must preserve meaning and direction.`
- Right-align the Arabic column and left-align the English column. Mirror their inner padding and keep a 1pt teal divider centered between them.
- Mixed Arabic/English runs must preserve Unicode character order and visible punctuation without converting text to outlines.

### SLIDE 15: Rotated Text
Multiple text boxes at different rotation angles: 0°, 45°, 90°, 135°, 270°. Supporting shapes aligned to the rotated text. Tests exact anchor points for rotated elements.

## Explicit v1 constraints

- Use the **Blank with Footer** layout with title `Rotation Atlas`.
- Create five text boxes labeled exactly `Baseline 0°`, `Diagonal 45°`, `Vertical 90°`, `Reverse 135°`, and `Vertical 270°`.
- Apply rotations of 0°, 45°, 90°, 135°, and 270° respectively. Each text box is 5cm × 1.5cm, uses Liberation Sans 16pt Bold, and has a matching 6cm × 2cm supporting rectangle sharing its center and rotation.
- Distribute the five pairs evenly from x=2cm through x=28cm on a common y=8cm anchor line. Keep text editable and store rotations in native OOXML transforms.

### SLIDE 16: Intentional Off-Canvas Bleed
Objects deliberately extending beyond the slide canvas edges — a large circle at (-3cm, -2cm) partly visible, a rectangle extending 5cm past the right edge. These are intentional design choices, not errors.

## Explicit v1 constraints

- Use the **Blank with Footer** layout with title `Beyond the Frame`.
- Place a 10cm diameter coral circle at (-3cm, -2cm), a 12cm × 6cm teal rectangle at (28.867cm, 6cm) so it extends 5cm beyond the right edge, and a 16cm × 3cm gold strip at (8cm, -1cm).
- Add on-canvas labels `INTENTIONAL BLEED` and `Negative coordinates are part of the composition.`
- Preserve negative and over-bound coordinates in OOXML. Do not replace the composition with a screenshot, hide content under opaque shapes, or move the objects fully on-canvas.

### SLIDE 17: Deep Grouping
3 levels of nested groups. Inner groups contain exactly 3 shapes each. Middle groups contain exactly 2 inner groups. Outer group wraps everything. Z-order must be exact within each nesting level.

## Explicit v1 constraints

- Use the **Blank with Footer** layout with title `Nested Systems`.
- Build one outer group containing three middle groups. Each middle group contains two inner groups; each inner group contains three leaf shapes (18 leaf shapes total).
- Use native group objects at all three levels. Label the middle groups `INPUT`, `PROCESS`, and `OUTPUT`; label inner groups `A1`, `A2`, `B1`, `B2`, `C1`, and `C2`.
- Within every inner group, z-order is circle below rounded rectangle below label. The full outer group's bounding box has top-left position (3cm, 3cm) and size 27cm × 13cm.

### SLIDE 18: Multi-Column Editorial
3-column magazine-style layout with mixed English/Japanese text. Each column has a header image (from assets), body text, and a pull quote. Pattern fill on the background of one column.

## Explicit v1 constraints

- Use the **Blank with Footer** layout with title `Three Cities / 三つの都市`.
- Build three equal 9.5cm-wide editorial columns with 0.9cm gutters. Each column contains a 9.5cm × 3.5cm approved header image, a heading, body copy, and a pull quote.
- Column images, left to right: `cityscape.png`, `texture-pattern.png`, `cityscape.png`. Center the crop of each image and do not use unlisted media.
- Headings: `Systems`, `システム`, `Shared Futures`. Include the exact Japanese line `生成されたスライドは構造と意味を保持します。`
- Apply the approved `texture-pattern.png` as a tiled background only to the center column at 20% opacity. Use 0.9cm gutters consistently.

### SLIDE 19: Repetition and Consistency
Visually identical to the design system — every element must match the master's font sizes, colors, spacing, and line weights exactly. Tests deck-wide consistency. Internal hyperlinks to Slides 1 and 5 (not external URLs).

## Explicit v1 constraints

- Use the **Content Slide** layout with title `Design System Audit`.
- Show five samples labeled `Typography`, `Palette`, `Spacing`, `Line Weight`, and `Navigation`. Each sample must use the deck-level tokens exactly: Carlito 36pt, Liberation Sans 18pt, navy `#1B2A4A`, coral `#E8634A`, teal `#2AACB8`, and a 0.5pt teal rule.
- Create two native internal hyperlinks: `Return to Cover` targets Slide 1 and `Meet the Team` targets Slide 5. Do not use external URLs.
- Footer line, company name, accent bar, and slide number remain inherited from the master/layout; do not duplicate them as slide-local shapes.

### SLIDE 20: Final Torture Slide
Everything combined: chart (line chart), table (3×6), approved image (cropped), Arabic + Japanese text, rotated text box at 45°, overlapping semi-transparent shapes, nested group, master-inherited footer, gradient fill, bullet list, slide number field — all on one slide.

## Explicit v1 constraints

- Use the **Blank with Footer** layout with title `Gloss Synthesis`.
- Add one native line chart with series `Structural`, `Visual`, and `Combined` across categories `L1`, `L2`, `L3`; values are `72, 84, 96`, `68, 82, 95`, and `70, 83, 97`.
- Add one native 3-row × 6-column table. Header: `Tier`, `Slides`, `Checks`, `SSIM`, `Schema`, `Status`; rows: `L1 | 5 | 70 | 0.9999 | Pass | Ready` and `L3 | 20 | 280 | 0.9999 | Pass | Ready`.
- Insert `hero-abstract.png` with a 20% left crop. Add Arabic `اختبار شامل` with native RTL direction and Japanese `総合テスト` in Noto Sans CJK JP.
- Include a 45° text box labeled `ROTATED`, three overlapping semi-transparent shapes inside a two-level group, a navy-to-teal gradient, a three-item bullet list, a live slide-number field, and the inherited master footer.

---

## Asset Manifest

The following images are bundled in `benchmark/assets/mirrored/`. Do NOT use any other images.

| Filename | Description | Approximate Size |
|----------|-------------|------------------|
| `hero-abstract.png` | Abstract geometric art for Slide 1 cover | 1920×1080 |
| `cityscape.png` | Procedural urban skyline illustration for image-crop tests | 2400×1600 |
| `texture-pattern.png` | Geometric texture for Slide 7 and Slide 18 | 800×800 |

*Assets are bundled in `benchmark/assets/mirrored/`; hashes and source metadata are recorded in the manifest.*

---

## Delivery and Validation

### Step 1: Author delivers the canonical reference deck
Deliver the prompt-authored file as `gloss-v1-gold.pptx` from the pinned LibreOffice environment.

### Step 2: Author self-check
Verify before delivery:
   - [ ] All fonts are from the approved list above
   - [ ] All images are from the asset manifest above
   - [ ] Slide size is 16:9 (33.867cm × 19.05cm)
   - [ ] Slides are numbered 1-20
   - [ ] No SmartArt, animations, transitions, audio, video, speaker notes, or comments
   - [ ] Master "Gloss Master" exists with footer line, slide number, and company name
   - [ ] Layouts "Title Slide", "Content Slide", "Two-Column", and "Blank with Footer" exist
   - [ ] Slides 1, 2, 4, 5, 9, 11, 12 use the correct layout (not manually placed elements)
   - [ ] Table on Slide 3 is a native table (not grouped shapes)
   - [ ] Chart on Slide 4 is a native chart (not an image or shapes)
   - [ ] Arabic text on Slide 6 has RTL paragraph direction set
   - [ ] Fields on Slide 12 are live fields (not static text)
   - [ ] Slide number on every slide comes from the master, not manually typed
   - [ ] Groups on Slides 2, 5, 8, 10, 17 are actual group objects

### Step 3: Canonical environment certification
After delivery, the benchmark maintainer will:
1. Open the `.pptx` in the pinned LibreOffice environment without document recovery.
2. Export all 20 slides to PNG at 1920×1080.
3. Run OOXML schema, structural, font, asset-hash, and anti-cheat validation.
4. Run repeated exports to establish deterministic self-similarity.
5. Publish grading-verified measurements separately from generation-attested metadata supplied by model submitters.

The file must not contain Calibri, Cambria, SmartArt, transitions, 3D rotation, or bevel effects. Use the bundled metric-compatible fonts and native constructs defined above. Keep charts standards-based and use only basic outer shadows; avoid glow and reflection effects.
