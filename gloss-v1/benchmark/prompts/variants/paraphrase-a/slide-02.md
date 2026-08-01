# Gloss v1 — Slide 02: Dense Agenda with Layout Semantics (alternative wording A)

The natural-language requirements that follow are the primary directive. Treat the reference image as supplementary visual guidance only.

**Layout:** "Content Slide" (from master)
**Tier:** Level 1

**Required construction:**

1. Select the "Content Slide" layout. Title and body must remain in the layout placeholders.

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

   Employ native paragraph-bullet properties. The shown `•` and `◦` characters specify the required bullet glyphs and are not literal characters in the paragraph text runs.

4. **Grouped icon-text rows**: Construct three icon-text rows on the right. Each row contains one 1cm teal circle and one time label. Put all six leaf objects directly in one flat group; do not create row subgroups. Align the group's top to the first bullet and bottom to the last bullet. Exact horizontal position and the two intermediate row gaps are intentionally unconstrained and unscored.
   - The three time labels, from top to bottom, are "09:00", "11:30", and "14:00" in Liberation Sans 14pt Bold `#FFFFFF`.
   - Each circle is filled with `#2AACB8`.

**Why this slide is hard for AI:**
- Evaluates bullet hierarchy (indentation, different bullet characters)
- Evaluates paragraph-level formatting (spacing, indent)
- Evaluates object grouping (the time column must be one group)
- Evaluates placeholder usage for title and body
- Evaluates alignment precision

---
