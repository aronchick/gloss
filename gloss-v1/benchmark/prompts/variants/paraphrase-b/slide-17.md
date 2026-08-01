# Gloss v1 — Slide 17: Deep Grouping (alternative wording B)

The primary directive is the following set of natural-language requirements. Consult the reference image solely for supplementary visual guidance.

3 levels of nested groups. Inner groups contain with exact precision 3 shapes each. Middle groups contain with exact precision 2 inner groups. Outer group wraps everything. Z-order must be exact within each nesting level.

## Exact v1 constraints

- Adopt the **Blank with Footer** layout with title `Nested Systems`.
- Build one outer group at (3cm, 3cm), size 27cm × 13cm, composed of three middle groups: `INPUT` at (3cm, 3cm), `PROCESS` at (13.219cm, 3cm), and `OUTPUT` at (23.438cm, 3cm). Each middle group is 6.562cm × 13cm and contains two inner groups.
- Set the six 6.562cm × 4.333cm inner groups at (3cm, 3cm), (3cm, 11.667cm), (13.219cm, 3cm), (13.219cm, 11.667cm), (23.438cm, 3cm), and (23.438cm, 11.667cm), labeled `A1`, `A2`, `B1`, `B2`, `C1`, and `C2` respectively.
- Each inner group contains with exact precision three leaf objects: a 45%-opaque colored circle at the bottom of z-order, an 85%-opaque rounded panel over it, and a centered Carlito 18pt Bold editable label on top. Choose navy for A1/B1/C1 and teal for A2/B2/C2. Maintain the middle-group label (`INPUT`, `PROCESS`, or `OUTPUT`) inside each panel.
- Choose native group objects at all three levels. Label the middle groups `INPUT`, `PROCESS`, and `OUTPUT`; label inner groups `A1`, `A2`, `B1`, `B2`, `C1`, and `C2`.
- Within every inner group, z-order is circle beneath rounded rectangle beneath label. Maintain the exact outer, middle, and inner group transforms instead of flattening the composition.
