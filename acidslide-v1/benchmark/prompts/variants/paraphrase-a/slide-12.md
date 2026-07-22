# AcidSlide v1 — Slide 12: Native Field Slide (alternative wording A)

The natural-language requirements that follow are the primary directive. Treat the reference image as supplementary visual guidance only.

**Layout:** "Content Slide"
**Tier:** Level 2

**Required construction:**

1. **Title** (placeholder): `Document Fields`

2. **Three field demonstrations** — each in its own text box:

   **Field 1 — Slide Number**:
   - Text box: "Current slide: " followed by an **inserted slide number field** (LibreOffice: Position → Field → Page Number)
   - Never type the number manually. It must remain a live field.
   - Liberation Sans 18pt `#FFFFFF`

   **Field 2 — Date/Time**:
   - `Generated: ` followed by a fixed native date/time field with value `2025-01-15T10:30:00Z`, displayed precisely as `2025-01-15 10:30 UTC`; Liberation Sans 18pt `#FFFFFF`.

   **Field 3 — Footer**:
   - The slide footer (from View → Header and Footer) should contain: "AcidSlide Benchmark v1"
   - This must be enabled via the master's footer placeholder

3. **Explanatory labels** next to each:
   - "← Live slide number field (not static text)"
   - "← Fixed date/time field"
   - "← Footer from master placeholder"
   - Liberation Sans 12pt Italic `#2AACB8`

4. **A static text comparison** — a text box that says "Slide 12" in the same font/size as Field 1, to highlight the difference between static text and a live field.

**Why this slide is hard for AI:**
- Evaluates native field insertion (not static text that looks like a field)
- Evaluates date/time field (the grader pins the datetime)
- Evaluates footer field from master
- The grader verifies field type in OOXML, not just rendered text

---

## Slides 13-20 (Level 3) — Brief Specifications
