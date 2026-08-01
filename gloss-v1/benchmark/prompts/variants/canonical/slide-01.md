# Gloss v1 — Slide 01: Cover / Title Stress Test

The natural-language requirements below are the primary directive. Use the reference image only as supplementary visual guidance.

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
