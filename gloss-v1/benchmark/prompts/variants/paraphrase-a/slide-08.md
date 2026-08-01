# Gloss v1 — Slide 08: Overlap, Shadow, and Transparency (alternative wording A)

The natural-language requirements that follow are the primary directive. Treat the reference image as supplementary visual guidance only.

**Layout:** "Blank with Footer"
**Tier:** Level 2

**Required construction:**

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

2. **Z-order** must remain precisely as listed: Card 1 at bottom, Card 5 on top.

3. **Group test**: Cards 1 and 2 should be grouped together. Cards 3, 4, and 5 should be grouped together. The two groups should NOT be grouped with each other.

4. **Gradient fill shape**: a rectangle at the bottom of the slide (y=15cm, full width, 3cm tall) with a linear gradient from `#0F1923` (left) to `#2AACB8` (right).

5. **Title**: "Depth & Layering" — Carlito 36pt Bold `#FFFFFF`, position (1.5cm, 0.5cm)

**Why this slide is hard for AI:**
- Evaluates precise z-order with 5 overlapping shapes
- Evaluates transparency at different levels
- Evaluates shadow parameters on every card
- Evaluates selective grouping (not all grouped, specific subsets)
- Evaluates gradient fill

---
