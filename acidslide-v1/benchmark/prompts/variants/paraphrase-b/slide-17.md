# AcidSlide v1 — Slide 17: Deep Grouping (alternative wording B)

The primary directive is the following set of natural-language requirements. Consult the reference image solely for supplementary visual guidance.

3 levels of nested groups. Inner groups contain with exact precision 3 shapes each. Middle groups contain with exact precision 2 inner groups. Outer group wraps everything. Z-order must be exact within each nesting level.

## Fixed v1 acceptance constraints

- Adopt the **Blank with Footer** layout with title `Nested Systems`.
- Build one outer group composed of three middle groups. Each middle group contains two inner groups; each inner group contains three leaf shapes (18 leaf shapes total).
- Choose native group objects at all three levels. Label the middle groups `INPUT`, `PROCESS`, and `OUTPUT`; label inner groups `A1`, `A2`, `B1`, `B2`, `C1`, and `C2`.
- Within every inner group, z-order is circle beneath rounded rectangle beneath label. The full outer group's bounding box has top-left position (3cm, 3cm) and size 27cm × 13cm.
