# Gloss v1 — Slide 06: Multilingual Editorial (alternative wording B)

The primary directive is the following set of natural-language requirements. Consult the reference image solely for supplementary visual guidance.

**Layout:** "Blank with Footer" (from master)
**Tier:** Level 2

**Acceptance-target composition:**

1. **Three text columns** side by side:

   **Column 1 — English** (left third):
   - Title: "Global Perspectives" in Carlito 24pt Bold `#FFFFFF`
   - Body (Liberation Sans 14pt `#F5F3EE`, left-aligned):
     ```
     The rapid advancement of language models
     has transformed how organizations approach
     document generation. From financial reports
     to marketing materials, AI-driven content
     creation is reshaping every industry.
     ```

   **Column 2 — Arabic RTL** (center third):
   - Title: "وجهات نظر عالمية" in Noto Sans Arabic 24pt Bold `#FFFFFF`
   - Body (Noto Sans Arabic 14pt `#F5F3EE`, **RIGHT-to-left aligned**):
     ```
     لقد أدى التقدم السريع في نماذج اللغة إلى تحويل
     كيفية تعامل المؤسسات مع إنشاء المستندات. من
     التقارير المالية إلى المواد التسويقية، يعيد إنشاء
     المحتوى المدعوم بالذكاء الاصطناعي تشكيل كل صناعة.
     ```
   - **CRITICAL**: This column must be set to RTL paragraph direction. The text must flow right-to-left. This is NOT just right-alignment — the paragraph direction property must be set to RTL.

   **Column 3 — Japanese** (right third):
   - Title: "グローバルな視点" in Noto Sans CJK JP 24pt Bold `#FFFFFF`
   - Body (Noto Sans CJK JP 14pt `#F5F3EE`, left-aligned):
     ```
     言語モデルの急速な進歩により、組織がドキュメント生成に
     取り組む方法が変革されました。財務報告からマーケティング
     資料まで、AI主導のコンテンツ作成はあらゆる産業を
     再形成しています。
     ```

2. **Decorative separator lines** between columns:
   - Vertical lines at x=11.2cm and x=22.5cm
   - Height: from y=3cm to y=16cm
   - Style: 1pt, `#2AACB8`, 50% opacity

3. **Callout box** overlapping the Arabic and Japanese columns:
   - Position: x=15cm, y=13cm
   - Size: 12cm × 4cm
   - Fill: `#E8634A` at 90% opacity
   - Text: "AI-generated slides must handle RTL text,\nCJK line breaking, and mixed scripts correctly."
   - Font: Liberation Sans 13pt Bold `#FFFFFF`, centered
   - Corner radius: 0.3cm
   - This callout should overlap both the Arabic and Japanese columns

**Why this slide is hard for AI:**
- Measures correct RTL paragraph direction (not just alignment)
- Measures CJK text rendering and line breaking
- Measures correct font assignment per script
- Measures overlap between callout and text columns
- Measures Unicode text preservation (exact characters must match)

---
