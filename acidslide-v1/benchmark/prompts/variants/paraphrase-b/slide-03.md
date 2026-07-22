# AcidSlide v1 — Slide 03: Native Table Stress Test (alternative wording B)

The primary directive is the following set of natural-language requirements. Consult the reference image solely for supplementary visual guidance.

**Layout:** "Blank with Footer" (from master)
**Tier:** Level 1

**Acceptance-target composition:**

1. **Title text box** (freestanding, NOT a placeholder — this slide uses Layout 4 which has no content placeholders):
   - Text: `Performance Metrics`
   - Font: Carlito 36pt Bold, `#FFFFFF`
   - Position: x=1.5cm, y=0.8cm

2. **Native table** — this must be implemented as a real LibreOffice Impress table, not shapes pretending to be a table:
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
   - Borders: 0.5pt `#2AACB8` between all cells, 2pt `#2AACB8` beneath header row
   - Q3 column: color each Q3 value `#2AACB8` when it meets the Target-column threshold and `#E8634A` when it misses that threshold.
     - Q3: Latency p50 (9 ≤ 10 ✓), p99 (58 ≤ 75 ✓), Throughput (1890 misses 2000 ✗), Error (0.04 ≤ 0.05 ✓), Uptime (99.98 ≥ 99.95 ✓), Cache (84 ≥ 80 ✓)

3. **Annotation callout** — a rounded rectangle with text, located next to the table:
   - Position: x=24cm, y=15.5cm
   - Size: 8cm × 2.5cm
   - Fill: `#E8634A`
   - Corner radius: 0.3cm
   - Text: "Throughput target\nmissed by 5.5%" in Liberation Sans 12pt Bold `#FFFFFF`, centered
   - A thin line (1pt, `#E8634A`) connecting the callout to the Q3 Throughput cell; connector routing is otherwise unconstrained.

4. **Paragraph indent**: the Metric-column paragraphs must employ a 0.5cm left paragraph indent in addition to cell padding. No tab character or tab-stop property is required.

**Why this slide is hard for AI:**
- Measures native table creation (not shapes)
- Measures cell-level formatting (conditional colors)
- Measures table borders (mixed weights)
- Measures tab stops and paragraph indentation inside table cells
- Measures annotation positioning relative to table cells

---
