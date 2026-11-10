# Document template baseline

A-10-T16 · Deliverable A-10 (design system & localisation baseline) · gap-43.

Xero runs three template systems, prints on US Letter with centimetre margins and previews with a
New Zealand sample customer. Numo9 has **one** template system for every PDF it produces.

| Rule | Value |
|---|---|
| Paper | Letter, 8.5 × 11 in (612 × 792 pt) |
| Margins | 1 in on every side; the footer sits inside the bottom margin |
| Header | Numo9 brand mark (black on yellow `#FFD100`, from `packages/ui/tokens/tokens.json`), tagline, issuer's legal name, address with Province and Postal code, GST/HST registration |
| Footer | "Prepared with Numo9" and "Page X of Y" (one translatable sentence) |
| Dates and money | Same formats as the web app: `26 Oct 2026` / `$1,234.56` (en-CA), `26 oct. 2026` / `1 234,56 $` (fr-CA) |
| Language | The recipient's locale (`numo9.i18n.locale.locale_for`); every label is a gettext message |
| Resources | Inline CSS and `data:` URIs only — the renderer refuses `file:`, `http(s):` and other URLs |
| Sample data | Canadian only: Refined Interiors Inc. (Toronto ON M5V 2T6) billing Maple Leaf Supply Ltd. (Ottawa ON), HST 13 % (ON) |

## Files

| File | Purpose |
|---|---|
| `backend/numo9/documents/templates/documents/base.html` | Page geometry, brand header, footer — every document extends it |
| `backend/numo9/documents/templates/documents/sample.html` | Sample document on the baseline |
| `backend/numo9/documents/pdf.py` | `render_pdf(template, context, locale=…)` → PDF bytes (WeasyPrint) |
| `backend/numo9/documents/formatting.py` | `format_date`, `format_money` for documents |
| `backend/numo9/documents/sample_data.py` | Canadian sample data for previews and tests |

## Adding a document (Phase 1: invoice, quote, credit note, PO, statement)

```django
{% extends "documents/base.html" %}
{% load i18n documents %}
{% block title %}{% translate "Invoice" %} {{ number }}{% endblock %}
{% block content %}… {{ total|money:document_locale }} … {{ due_date|docdate:document_locale }} …{% endblock %}
```

Never set `@page` size or margins in a child template.

## Preview

```bash
python manage.py render_sample_document --out sample.pdf            # English (Canada)
python manage.py render_sample_document --out sample-fr.pdf --locale fr-ca
```

The backend image installs Pango, HarfBuzz and the Inter and DejaVu fonts that WeasyPrint needs.

## Tests

`backend/tests/test_documents_pdf.py` (pytest; `gap-43`): every page measures 612 × 792 pt, all
body text lies inside the 1 in margins, the sample data is Canadian, the French document uses
French dates, money and page counter, the brand colours match the design tokens, and external
resources are refused.
