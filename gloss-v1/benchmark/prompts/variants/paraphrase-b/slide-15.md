# Gloss v1 — Slide 15: Rotated Text (alternative wording B)

The primary directive is the following set of natural-language requirements. Consult the reference image solely for supplementary visual guidance.

Multiple text boxes at different rotation angles: 0°, 45°, 90°, 135°, 270°. Supporting shapes aligned to the rotated text. Measures exact anchor points for rotated elements.

## Exact v1 constraints

- Adopt the **Blank with Footer** layout with title `Rotation Atlas`.
- Produce five text boxes labeled with exact precision `Baseline 0°`, `Diagonal 45°`, `Vertical 90°`, `Reverse 135°`, and `Vertical 270°`.
- Draw a 0.5pt teal alignment rule from (1.5cm, 8cm) to (32cm, 8cm), behind every object.
- Assign rotations of 0°, 45°, 90°, 135°, and 270° respectively. Each text box is 5cm × 1.5cm at y=7.25cm and uses centered Liberation Sans 16pt Bold. Set their x positions to 1.5cm, 7.5cm, 13.5cm, 19.5cm, and 25.5cm.
- Set a matching 6cm × 2cm supporting rectangle behind each text box at y=7cm and x=1cm, 7cm, 13cm, 19cm, and 25cm. Choose navy, teal, coral, gold, and navy fills respectively at 70% opacity. Each rectangle shares its text box’s center and rotation. Maintain text editable and store rotations in native transforms.
