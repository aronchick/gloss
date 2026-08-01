# Gloss v1 — Slide 09: Dense Text Overflow (alternative wording B)

The primary directive is the following set of natural-language requirements. Consult the reference image solely for supplementary visual guidance.

**Layout:** "Content Slide"
**Tier:** Level 2

**Acceptance-target composition:**

1. **Title** (placeholder): `API Reference`

2. **Two narrow text columns** (each 14cm × 14cm, side by side):

   **Left column** — text box with NO auto-fit (text should clip if it overflows):
   - AutoFit: OFF (resize shape to fit text: OFF, shrink text on overflow: OFF)
   - Text (Liberation Mono 11pt, `#F5F3EE`, left-aligned):
     ```
     GET /api/v1/submissions
     Authorization: Bearer YOUR_TOKEN_HERE
     Content-Type: application/json
     
     Query Parameters:
       model_id    string  required  Filter by model
       tier        integer optional  1, 2, or 3
       status      string  optional  queued|grading|completed
       limit       integer optional  Default: 20, max: 100
       offset      integer optional  Default: 0
     
     Response 200:
     (
       "submissions": [
         (
           "id": "sub_abc123",
           "model_id": "gpt-4o",
           "tier": 3,
           "status": "completed",
           "fidelity_score": 0.847,
           "created_at": "2025-01-15T10:30:00Z"
         )
       ],
       "total": 142,
       "has_more": true
     )
     ```

   Authoring instruction; do not place this note on the slide. In the left column's slide text, replace the six JSON-structural parentheses shown in the fenced example with `{` and `}`. Maintain all other characters.

   **Right column** — text box WITH auto-shrink enabled:
   - AutoFit: Shrink text on overflow = ON
   - Same text content as left column but with this additional block appended:
     ```
     
     Error Responses:
       401 Unauthorized - Invalid or expired token
       403 Forbidden - Rate limit exceeded
       404 Not Found - Submission not found
       422 Unprocessable - Invalid parameters
       500 Internal Server Error - Contact support
     
     Rate Limits:
       Free tier: 10 req/min, 100 req/hour
       Pro tier:  60 req/min, 1000 req/hour
       Enterprise: Custom
     ```

3. **Column labels** over each:
   - "Fixed Size (clips)" over left column — Liberation Sans 11pt Bold `#E8634A`
   - "Auto-Shrink (fits)" over right column — Liberation Sans 11pt Bold `#2AACB8`

4. **Line spacing**: with exact precision 1.15× throughout both columns.

**Why this slide is hard for AI:**
- Measures autofit behavior (one column clips, one shrinks)
- Measures monospaced text with exact indentation
- Measures dense text layout with no autofit tricks
- Measures line spacing precision
- Measures that text content is preserved with exact precision (including whitespace)

---
