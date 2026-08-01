# Gloss v1 — Slide 12: Native Field Slide (alternative wording B)

The primary directive is the following set of natural-language requirements. Consult the reference image solely for supplementary visual guidance.

**Layout:** "Content Slide"
**Tier:** Level 2

**Acceptance-target composition:**

1. **Title** (placeholder): `Document Fields`

2. **Three field demonstrations** — each in its own text box:

   **Field 1 — Slide Number**:
   - Text box: "Current slide: " followed by an **inserted slide number field** (LibreOffice: Embed → Field → Page Number)
   - Do not ever type the number manually. It must be implemented as a live field.
   - Liberation Sans 18pt `#FFFFFF`

   **Field 2 — Date/Time**:
   - `Generated: ` followed by a fixed native date/time field with value `2025-01-15T10:30:00Z`, displayed with exact precision as `2025-01-15 10:30 UTC`; Liberation Sans 18pt `#FFFFFF`.

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
- Measures native field insertion (not static text that looks like a field)
- Measures date/time field (the grader pins the datetime)
- Measures footer field from master
- The grader verifies field type in OOXML, not just rendered text

---

## Slides 13-20 (Level 3) — Exact Specifications
