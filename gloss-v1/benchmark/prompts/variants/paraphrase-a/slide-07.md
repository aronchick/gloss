# Gloss v1 — Slide 07: Image Crop and Mask (alternative wording A)

The natural-language requirements that follow are the primary directive. Treat the reference image as supplementary visual guidance only.

**Layout:** "Blank with Footer"
**Tier:** Level 2

**Required construction:**

1. **Three images** from the asset manifest, each cropped differently:

   - **Image A**: `benchmark/assets/mirrored/cityscape.png`
     - Size on slide: 10cm × 8cm, position (1.5cm, 2cm)
     - Crop: remove top 15% and bottom 10% of original image
     - No shape mask

   - **Image B**: `benchmark/assets/mirrored/cityscape.png` (same image, different crop)
     - Size on slide: 8cm × 8cm, position (13cm, 2cm)
     - Crop: remove left 30% of original image
     - Set **circle crop mask** (crop to ellipse shape)

   - **Image C**: `benchmark/assets/mirrored/texture-pattern.png`
     - Size on slide: 10cm × 8cm, position (22.5cm, 2cm)
     - Crop: remove right 25% of original image
     - Set **rounded rectangle crop mask** with 1cm corner radius

2. **Caption text boxes** under each image:
   - "Full panorama crop" / "Circle-masked detail" / "Rounded corner crop"
   - Liberation Sans 12pt Italic `#F5F3EE`, centered under each image

3. **Overlapping layer test** — place a semi-transparent rectangle OVER Image B:
   - Size: 6cm × 6cm
   - Position: centered on Image B
   - Fill: `#1B2A4A` at 50% opacity
   - Text: "PREVIEW" in Carlito 24pt Bold `#FFFFFF`, centered
   - This rectangle must be ABOVE Image B in z-order

4. **Title**: "Image Handling" in Carlito 36pt Bold `#FFFFFF` at position (1.5cm, 0.5cm)

**Why this slide is hard for AI:**
- Evaluates different crop rectangles on the same image
- Evaluates crop-to-shape (circle, rounded rectangle)
- Evaluates z-order with semi-transparent overlay on an image
- Evaluates that images come from the approved asset manifest (hash verification)

---
