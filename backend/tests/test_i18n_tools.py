"""Tests for backend/tools check_i18n, check_glossary and catalogue helpers (S-01-T10)."""

import json
from pathlib import Path

import pytest

from tools import check_glossary, check_i18n
from tools.i18n_catalogs import flatten, parse_po, unflatten

PO_HEADER = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _po(*msgids: str) -> str:
    return PO_HEADER + "".join(f'msgid "{m}"\nmsgstr ""\n\n' for m in msgids)


# ---- catalogue helpers -------------------------------------------------------------------


def test_flatten_and_unflatten_round_trip() -> None:
    tree = {"home": {"title": "Home"}, "shell": {"nav": {"main": "Main"}}}
    flat = flatten(tree)
    assert flat == {"home.title": "Home", "shell.nav.main": "Main"}
    assert unflatten(flat) == tree


def test_unflatten_rejects_message_that_is_also_a_group() -> None:
    with pytest.raises(ValueError, match="both a message and a group"):
        unflatten({"home": "Home", "home.title": "Title"})


def test_parse_po_handles_context_plural_multiline_and_obsolete() -> None:
    text = (
        PO_HEADER
        + 'msgctxt "menu"\nmsgid "Open"\nmsgstr ""\n\n'
        + 'msgid "%(n)s item"\nmsgid_plural "%(n)s items"\nmsgstr[0] ""\nmsgstr[1] ""\n\n'
        + 'msgid ""\n"Long "\n"text"\nmsgstr "Texte"\n\n'
        + '#~ msgid "Gone"\n#~ msgstr ""\n'
    )
    entries = parse_po(text)
    assert [e.key for e in entries] == ["menu\x04Open", "%(n)s item", "Long text"]
    assert entries[1].msgid_plural == "%(n)s items"
    assert entries[2].msgstr == ("Texte",)


# ---- check_i18n frontend -----------------------------------------------------------------


def _frontend(
    tmp_path: Path, extracted: dict[str, str], en: dict[str, str], fr: dict[str, str]
) -> tuple[Path, Path]:
    ex = _write(
        tmp_path / "extracted.json",
        json.dumps({k: {"defaultMessage": v} for k, v in extracted.items()}),
    )
    messages = tmp_path / "messages"
    _write(messages / "en-CA.json", json.dumps(unflatten(en)))
    _write(messages / "fr-CA.json", json.dumps(unflatten(fr)))
    return ex, messages


def test_frontend_ok_when_catalogues_match(tmp_path: Path) -> None:
    ex, messages = _frontend(
        tmp_path, {"home.title": "Home"}, {"home.title": "Home"}, {"home.title": "Accueil"}
    )
    assert check_i18n.check_frontend(ex, messages, write=False) == []


@pytest.mark.parametrize("missing_in", ["en-CA", "fr-CA"])
def test_frontend_missing_key_fails(tmp_path: Path, missing_in: str) -> None:
    en = {} if missing_in == "en-CA" else {"home.title": "Home"}
    fr = {} if missing_in == "fr-CA" else {"home.title": "Home"}
    ex, messages = _frontend(tmp_path, {"home.title": "Home"}, en, fr)
    errors = check_i18n.check_frontend(ex, messages, write=False)
    assert f"home.title: missing in {missing_in}.json" in errors


def test_frontend_source_and_en_catalogue_divergence_fails(tmp_path: Path) -> None:
    ex, messages = _frontend(
        tmp_path, {"home.title": "Home"}, {"home.title": "Start"}, {"home.title": "Home"}
    )
    errors = check_i18n.check_frontend(ex, messages, write=False)
    assert any("source defaultMessage is 'Home'" in e for e in errors)


def test_frontend_generated_hash_id_fails(tmp_path: Path) -> None:
    ex, messages = _frontend(tmp_path, {"Xy9aB2": "Home"}, {"Xy9aB2": "Home"}, {"Xy9aB2": "Home"})
    errors = check_i18n.check_frontend(ex, messages, write=False)
    assert any("dotted lower-camel key" in e for e in errors)


def test_frontend_fr_only_key_fails(tmp_path: Path) -> None:
    ex, messages = _frontend(
        tmp_path, {"home.title": "Home"}, {"home.title": "Home"}, {"home.title": "H", "x.y": "Z"}
    )
    assert "x.y: in fr-CA.json but not in en-CA.json" in check_i18n.check_frontend(
        ex, messages, write=False
    )


def test_frontend_write_adds_missing_keys_with_english_placeholder(tmp_path: Path) -> None:
    ex, messages = _frontend(tmp_path, {"home.title": "Home"}, {}, {})
    assert check_i18n.check_frontend(ex, messages, write=True) == []
    fr = json.loads((messages / "fr-CA.json").read_text(encoding="utf-8"))
    assert fr == {"home": {"title": "Home"}}
    assert check_i18n.check_frontend(ex, messages, write=False) == []


# ---- check_i18n backend ------------------------------------------------------------------


def _locale(root: Path, en: tuple[str, ...], fr: tuple[str, ...]) -> Path:
    _write(root / "en_CA/LC_MESSAGES/django.po", _po(*en))
    _write(root / "fr_CA/LC_MESSAGES/django.po", _po(*fr))
    return root


def test_backend_ok_when_committed_matches_generated(tmp_path: Path) -> None:
    committed = _locale(tmp_path / "c", ("Hello",), ("Hello",))
    generated = _locale(tmp_path / "g", ("Hello",), ("Hello",))
    assert check_i18n.check_backend(committed, generated) == []


def test_backend_new_source_string_not_in_committed_catalogue_fails(tmp_path: Path) -> None:
    committed = _locale(tmp_path / "c", ("Hello",), ("Hello",))
    generated = _locale(tmp_path / "g", ("Hello", "New"), ("Hello", "New"))
    errors = check_i18n.check_backend(committed, generated)
    assert any("missing msgid 'New'" in e for e in errors)


def test_backend_en_fr_mismatch_fails(tmp_path: Path) -> None:
    committed = _locale(tmp_path / "c", ("Hello", "Extra"), ("Hello",))
    generated = _locale(tmp_path / "g", ("Hello", "Extra"), ("Hello",))
    assert "msgid 'Extra' only in en_CA catalogue" in check_i18n.check_backend(committed, generated)


def test_backend_uncommitted_catalogue_fails(tmp_path: Path) -> None:
    generated = _locale(tmp_path / "g", ("Hello",), ("Hello",))
    errors = check_i18n.check_backend(tmp_path / "empty", generated)
    assert any("not committed" in e for e in errors)


# ---- check_glossary ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Enter the VAT number",
        "Value added tax",
        "State",
        "ZIP",
        "Zip code",
        "Annual leave balance",
        "Organization settings",
        "organizations",
        "Print Checks",
        "Your Advisor",
    ],
)
def test_glossary_flags_banned_terms(text: str) -> None:
    terms = check_glossary.load_glossary()
    assert check_glossary.scan({"k.x": text}, terms, "t"), text


@pytest.mark.parametrize(
    "text",
    [
        "Organisation settings",
        "organisations",
        "Province",
        "Postal code",
        "GST/HST",
        "Print cheques",
        "statement of account",
        "check your email",
        "Upload a .zip archive",
    ],
)
def test_glossary_accepts_en_ca_terms(text: str) -> None:
    terms = check_glossary.load_glossary()
    assert check_glossary.scan({"k.x": text}, terms, "t") == [], text


def test_glossary_allow_list_exempts_key(tmp_path: Path) -> None:
    glossary = _write(
        tmp_path / "g.toml",
        '[[banned]]\nterm = "VAT"\npattern = \'\\bVAT\\b\'\nuse = "GST/HST"\n'
        'allow = ["legal.foreignVat"]\n',
    )
    terms = check_glossary.load_glossary(glossary)
    assert check_glossary.scan({"legal.foreignVat": "EU VAT"}, terms, "t") == []
    assert check_glossary.scan({"other.key": "EU VAT"}, terms, "t")


def test_committed_catalogues_pass_all_checks() -> None:
    assert check_glossary.main([]) == 0


# ---- A-10-T15: glossary lint gates (gap-31 Canadian terms, gap-38 one spelling) --------------


@pytest.mark.gap("gap-31")
@pytest.mark.parametrize(
    "text",
    [
        "Enter the VAT number",
        "State",
        "ZIP code",
        "Annual leave balance",
        "Print Checks",
        "Enter the postcode",
        "Postal Code",
        "HST/GST registration",
        "GST-HST number",
        "Order a checkbook",
    ],
)
def test_gap_31_non_canadian_terms_fail(text: str) -> None:
    assert check_glossary.scan({"k.x": text}, check_glossary.load_glossary(), "t"), text


@pytest.mark.gap("gap-38")
@pytest.mark.parametrize("text", ["Organization settings", "3 organizations", "Your Advisor"])
def test_gap_38_spelling_flips_fail(text: str) -> None:
    assert check_glossary.scan({"k.x": text}, check_glossary.load_glossary(), "t"), text


@pytest.mark.gap("gap-31", "gap-38")
def test_gap_31_38_committed_text_uses_the_en_ca_glossary() -> None:
    """Catalogues (frontend en-CA, backend en_CA) and the design system's stories/fixtures."""
    assert check_glossary.main([]) == 0


@pytest.mark.gap("gap-31", "gap-38")
def test_preferred_terms_pass_and_every_ban_points_to_one() -> None:
    terms = check_glossary.load_glossary()
    preferred = check_glossary.load_preferred()
    names = {p.term for p in preferred}
    assert {"organisation", "cheque", "Province", "Postal code", "GST/HST", "vacation pay"} <= names
    for term in preferred:
        assert check_glossary.scan({"k": term.term}, terms, "t") == [], term.term
    for ban in terms:
        assert any(p.term.lower() in ban.use.lower() for p in preferred), ban.term


def test_glossary_scans_story_and_fixture_text_not_code(tmp_path: Path) -> None:
    src = tmp_path / "src" / "widgets"
    src.mkdir(parents=True)
    (src / "Widget.stories.tsx").write_text(
        'import { ZIP } from "./zip"; // ZIP code helper\n'
        "/* State machine */\n"
        'export const A = () => <label title="Your ZIP">Postal code</label>;\n'
        "export const B = () => <p>Choose your State</p>;\n",
        encoding="utf-8",
    )
    (src / "fixtures.ts").write_text('export const t = "Organization";\n', encoding="utf-8")
    (src / "Widget.tsx").write_text('export const ignored = "VAT";\n', encoding="utf-8")
    texts = check_glossary.source_texts(tmp_path / "src")
    problems = check_glossary.scan(texts, check_glossary.load_glossary(), "ui")
    assert len(problems) == 3, problems
    assert any("Widget.stories.tsx:3" in p and "ZIP" in p for p in problems)
    assert any("Widget.stories.tsx:4" in p and "State" in p for p in problems)
    assert any("fixtures.ts:1" in p for p in problems)


def test_glossary_terms_markdown() -> None:
    table = check_glossary.glossary_markdown()
    assert "| Postal code |" in table and "| VAT |" in table


def test_glossary_doc_page_is_current() -> None:
    page = (check_glossary.REPO_ROOT / "docs" / "design" / "glossary.md").read_text("utf-8")
    assert check_glossary.glossary_markdown() in page, "run check_glossary.py --terms"
