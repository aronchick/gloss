# AcidSlide v1 — Slide 10: Connector and Alignment Diagram (alternative wording A)

The natural-language requirements that follow are the primary directive. Treat the reference image as supplementary visual guidance only.

**Layout:** "Blank with Footer"
**Tier:** Level 2

**Required construction:**

1. **Architecture diagram** using ONLY built-in shapes and connectors:

   **Boxes** (all rounded rectangles, 5cm × 3cm, corner radius 0.3cm):

   | Box | Label | Position | Fill |
   |-----|-------|----------|------|
   | Client | "Client App" | (2cm, 3cm) | `#2AACB8` |
   | API Gateway | "API Gateway" | (14cm, 3cm) | `#1B2A4A` |
   | Auth | "Auth Service" | (8cm, 9cm) | `#E8634A` |
   | Grader | "Grader" | (20cm, 9cm) | `#E8634A` |
   | Queue | "Job Queue" | (14cm, 9cm) | `#D4A843` |
   | Storage | "Object Store" | (14cm, 15cm) | `#1B2A4A` |
   | DB | "PostgreSQL" | (6cm, 15cm) | `#1B2A4A` |
   | LB | "Leaderboard" | (22cm, 15cm) | `#2AACB8` |

   No pair of architecture boxes overlaps.

   All box text: Liberation Sans 12pt Bold `#FFFFFF`, centered.

2. **Connectors** — use native connectors (Position → Connector in LibreOffice), NOT plain lines:
   - Client → API Gateway (straight connector, arrow at end)
   - API Gateway → Auth (elbow connector, arrow at end)
   - API Gateway → Queue (straight connector, arrow at end)
   - Queue → Grader (straight connector, arrow at end)
   - Grader → Storage (straight connector, arrow at end)
   - Storage → DB (straight connector, arrow at end)
   - Storage → LB (straight connector, arrow at end)

   All connectors: 1.5pt, `#F5F3EE`, with arrowhead at destination end.

3. **Labels on connectors** — small text boxes placed near each connector:
   - Client→Gateway: "HTTPS" (Liberation Sans 10pt `#FFFFFF`)
   - Gateway→Auth: "JWT verify" (Liberation Sans 10pt `#FFFFFF`)
   - Gateway→Queue: "Enqueue" (Liberation Sans 10pt `#FFFFFF`)

4. **Nested grouping**:
   - Group 1: Auth + Queue + Grader boxes (label this group with a thin dashed border, 0.5pt `#FFFFFF` at 30%, and text "Processing Layer" over)
   - Group 2: Storage + DB + LB boxes (label with "Persistence Layer")
   - Group 3: Group 1 + Group 2 (the "Backend" super-group)

5. **Title**: "System Architecture" — Carlito 36pt Bold `#FFFFFF`, position (1.5cm, 0.5cm)

**Why this slide is hard for AI:**
- Evaluates native connectors (not plain lines)
- Evaluates nested grouping (groups inside groups)
- Evaluates precise alignment grid
- Evaluates connector routing between boxes
- Evaluates label positioning relative to connectors

---
