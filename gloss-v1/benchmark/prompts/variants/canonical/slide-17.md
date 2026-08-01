# Gloss v1 — Slide 17: Deep Grouping

The natural-language requirements below are the primary directive. Use the reference image only as supplementary visual guidance.

3 levels of nested groups. Inner groups contain exactly 3 shapes each. Middle groups contain exactly 2 inner groups. Outer group wraps everything. Z-order must be exact within each nesting level.

## Exact v1 constraints

- Use the **Blank with Footer** layout with title `Nested Systems`.
- Build one outer group at (3cm, 3cm), size 27cm × 13cm, containing three middle groups: `INPUT` at (3cm, 3cm), `PROCESS` at (13.219cm, 3cm), and `OUTPUT` at (23.438cm, 3cm). Each middle group is 6.562cm × 13cm and contains two inner groups.
- Place the six 6.562cm × 4.333cm inner groups at (3cm, 3cm), (3cm, 11.667cm), (13.219cm, 3cm), (13.219cm, 11.667cm), (23.438cm, 3cm), and (23.438cm, 11.667cm), labeled `A1`, `A2`, `B1`, `B2`, `C1`, and `C2` respectively.
- Each inner group contains exactly three leaf objects: a 45%-opaque colored circle at the bottom of z-order, an 85%-opaque rounded panel above it, and a centered Carlito 18pt Bold editable label on top. Use navy for A1/B1/C1 and teal for A2/B2/C2. Keep the middle-group label (`INPUT`, `PROCESS`, or `OUTPUT`) inside each panel.
- Use native group objects at all three levels. Label the middle groups `INPUT`, `PROCESS`, and `OUTPUT`; label inner groups `A1`, `A2`, `B1`, `B2`, `C1`, and `C2`.
- Within every inner group, z-order is circle below rounded rectangle below label. Preserve the exact outer, middle, and inner group transforms instead of flattening the composition.
