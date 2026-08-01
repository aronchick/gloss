# Gloss v1 — Slide 17: Deep Grouping

The natural-language requirements below are the primary directive. Use the reference image only as supplementary visual guidance.

3 levels of nested groups. Inner groups contain exactly 3 shapes each. Middle groups contain exactly 2 inner groups. Outer group wraps everything. Z-order must be exact within each nesting level.

## Explicit v1 constraints

- Use the **Blank with Footer** layout with title `Nested Systems`.
- Build one outer group containing three middle groups. Each middle group contains two inner groups; each inner group contains three leaf shapes (18 leaf shapes total).
- Use native group objects at all three levels. Label the middle groups `INPUT`, `PROCESS`, and `OUTPUT`; label inner groups `A1`, `A2`, `B1`, `B2`, `C1`, and `C2`.
- Within every inner group, z-order is circle below rounded rectangle below label. The full outer group's bounding box has top-left position (3cm, 3cm) and size 27cm × 13cm.
