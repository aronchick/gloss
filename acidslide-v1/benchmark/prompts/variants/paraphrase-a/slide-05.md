# AcidSlide v1 — Slide 05: Master Reuse Enforcement (alternative wording A)

The natural-language requirements that follow are the primary directive. Treat the reference image as supplementary visual guidance only.

**Layout:** "Content Slide" (from master)
**Tier:** Level 1

**Required construction:**

This slide's purpose is to verify that the master/layout is being used correctly, not just visually copied.

1. **Title** (placeholder): `Our Team`

2. **Body content** — three team member cards arranged horizontally:

   Each card is a group that includes:
   - A rounded rectangle: 9cm × 13cm, fill `#161F2E`, corner radius 0.3cm, border 1pt `#2AACB8`
   - Circle placeholder for photo: 4cm diameter, centered at top of card, fill `#1B2A4A` with text "Photo" in center (Liberation Sans 12pt `#FFFFFF`) — since we have no actual photos
   - Name: Carlito 18pt Bold `#FFFFFF`, centered
   - Title: Liberation Sans 14pt `#E8634A`, centered
   - Description: Liberation Sans 12pt `#F5F3EE`, centered, max 3 lines

   **Card 1:**
   - Name: "Sarah Chen"
   - Title: "Chief Architect"
   - Description: "15 years building distributed systems at scale"

   **Card 2:**
   - Name: "Marcus Rivera"
   - Title: "Head of Design"
   - Description: "Formerly at Apple, obsessed with pixel-perfect interfaces"

   **Card 3:**
   - Name: "Yuki Tanaka"
   - Title: "ML Engineering Lead"
   - Description: "PhD in NLP, built the model serving infrastructure"

   Cards placed at x=1.5cm, x=12cm, x=22.5cm — evenly spaced across the slide.

3. **Non-negotiable requirement**: The bottom footer line, "ACIDSLIDE" text, and slide number must originate from the master. Never manually add these elements on this slide. The whole point of this slide is to test that the master is correctly inherited.

4. **The accent bar** on the left edge must also come from the "Content Slide" layout, not a manually placed shape.

**Why this slide is hard for AI:**
- Evaluates that repeated elements (footer, line, text, slide number) come from master inheritance
- Evaluates grouped objects (each card is a group)
- Evaluates precise horizontal distribution of equal-sized elements
- Evaluates placeholder text formatting within groups

---
