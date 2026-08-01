# Gloss v1 — Slide 17: Deep Grouping (alternative wording A)

The natural-language requirements that follow are the primary directive. Treat the reference image as supplementary visual guidance only.

3 levels of nested groups. Inner groups contain precisely 3 shapes each. Middle groups contain precisely 2 inner groups. Outer group wraps everything. Z-order must be exact within each nesting level.

## Exact v1 constraints

- Select the **Blank with Footer** layout with title `Nested Systems`.
- Build one outer group at (3cm, 3cm), size 27cm × 13cm, that includes three middle groups: `INPUT` at (3cm, 3cm), `PROCESS` at (13.219cm, 3cm), and `OUTPUT` at (23.438cm, 3cm). Each middle group is 6.562cm × 13cm and contains two inner groups.
- Position the six 6.562cm × 4.333cm inner groups at (3cm, 3cm), (3cm, 11.667cm), (13.219cm, 3cm), (13.219cm, 11.667cm), (23.438cm, 3cm), and (23.438cm, 11.667cm), labeled `A1`, `A2`, `B1`, `B2`, `C1`, and `C2` respectively.
- Each inner group contains precisely three leaf objects: a 45%-opaque colored circle at the bottom of z-order, an 85%-opaque rounded panel over it, and a centered Carlito 18pt Bold editable label on top. Employ navy for A1/B1/C1 and teal for A2/B2/C2. Ensure the middle-group label (`INPUT`, `PROCESS`, or `OUTPUT`) inside each panel.
- Employ native group objects at all three levels. Label the middle groups `INPUT`, `PROCESS`, and `OUTPUT`; label inner groups `A1`, `A2`, `B1`, `B2`, `C1`, and `C2`.
- Within every inner group, z-order is circle under rounded rectangle under label. Retain the exact outer, middle, and inner group transforms instead of flattening the composition.
