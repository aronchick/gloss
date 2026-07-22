# AcidSlide v1 — Slide 11: Theme vs Local Override

The natural-language requirements below are the primary directive. Use the reference image only as supplementary visual guidance.

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
