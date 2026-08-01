# Gloss v1 — Slide 14: RTL-Heavy Comparison

The natural-language requirements below are the primary directive. Use the reference image only as supplementary visual guidance.

Two-column layout with heavy Arabic text on left (5+ paragraphs with mixed Arabic/English), English summary on right. Bidirectional text within single paragraphs (e.g., "The الذكاء الاصطناعي revolution"). Mirrored alignment: Arabic column is right-aligned, English column is left-aligned.

## Exact v1 constraints

- Use the **Two-Column** layout with title `RTL Systems Review`.
- Put the Arabic column at (1.5cm, 3.2cm), size 14cm × 12cm, in Noto Sans Arabic 14pt with native RTL paragraph direction and right alignment. Use six paragraphs exactly: `مراجعة الأنظمة الموزعة`; `دقة العرض هي أساس المقارنة بين الأنظمة.`; `سلامة البنية تحافظ على المعنى والتفاعل.`; `The الذكاء الاصطناعي revolution تتطلب نصاً ثنائي الاتجاه.`; `الإصدار Gloss v1 يختبر التوافق.`; and `يجب الحفاظ على علامات الترقيم وترتيب Unicode.`
- Put the English column at (18.5cm, 3.2cm), size 13.5cm × 12cm, in Liberation Sans 14pt with left alignment. Use five paragraphs exactly: `A structural benchmark must preserve meaning and direction.`; `Rendering alone cannot prove native editability.`; `Bidirectional runs must retain their Unicode order.`; `Mirrored padding makes the comparison deliberate.`; and `The benchmark records both artifact and visual fidelity.`
- Keep a 1pt teal divider at x=16.9cm from y=3cm through y=15.5cm. Mirror the columns’ inner padding around that divider.
- Mixed Arabic/English runs must preserve Unicode character order and visible punctuation without converting text to outlines.
