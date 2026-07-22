# AcidSlide v1 — Slide 04: Native Chart Stress Test (alternative wording B)

The primary directive is the following set of natural-language requirements. Consult the reference image solely for supplementary visual guidance.

**Layout:** "Content Slide" (from master)
**Tier:** Level 1

**Acceptance-target composition:**

1. **Title** (placeholder): `Revenue Growth`

2. **Native chart** — must be implemented as a real LibreOffice Impress chart, not shapes/images:
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

   - Callout 1: located over the "Asia Pacific 2024" bar
     - Rounded rectangle, 5cm × 2cm
     - Fill: `#2AACB8`
     - Text: "+62.9% YoY" in Liberation Sans 14pt Bold `#FFFFFF`
     - Arrow connector pointing from callout to the bar

   - Callout 2: located over the "Middle East & Africa 2024" bar
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
- Measures native chart creation with specific chart type
- Measures chart formatting (colors, labels, gridlines, legend)
- Measures chart data accuracy
- Measures overlay shapes on top of chart
- Measures connector arrows between callouts and chart elements

---
