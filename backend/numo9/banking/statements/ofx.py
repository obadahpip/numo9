"""OFX / QFX / QBO parser (F-02-T04).

**Why not ofxparse.** The plan names ``ofxparse``; its last release (0.21) builds a BeautifulSoup
tree of the whole file, calls APIs BeautifulSoup has deprecated, and took more than two minutes
on a 50,000-line file here — the import must take less than 60 s (F-02-T09). This small
tokenizer reads the same files in about a second and is tolerant where banks are sloppy.

One reader for the three formats — QFX (Quicken) and QBO (QuickBooks) are OFX with an Intuit
header and a few ``INTU.*`` elements:

- **header stripped**: everything before ``<OFX>`` is header — the OFX 1.x SGML header
  (``OFXHEADER:100`` … ``NEWFILEUID``), the OFX 2.x XML prolog, the Intuit header of QBO/QFX
  files, a byte-order mark, blank lines. The header only hints at the encoding, and banks get it
  wrong: valid UTF-8 bytes are read as UTF-8 (whatever ``CHARSET`` says), anything else as the
  declared single-byte charset (``8859-1`` → Latin-1), Windows-1252 by default;
- **SGML and XML bodies**: OFX 1.x leaves (``<TRNAMT>-4.25``) have no closing tag, aggregates
  (``<STMTTRN>`` … ``</STMTTRN>``) do — and some banks forget those too: a closing tag closes
  every open element down to its opening one, a stray closing tag is ignored, and a new
  ``<STMTTRN>`` closes an unclosed previous one. Entities (``&amp;``) are decoded;
- **statements**: bank (``STMTRS``) and credit-card (``CCSTMTRS``) statements. The amounts
  (``TRNAMT``) are already signed from the account holder's side. A file with several accounts
  gives the first one (or the one whose account number ends with the bank account's last four
  digits) and a warning;
- **lines**: ``DTPOSTED`` (``DTUSER`` when missing; ``20260603``, ``20260603120000.000[-5:EST]``),
  ``TRNAMT``, ``NAME`` / ``PAYEE.NAME`` (payee; the description is the name and the memo),
  ``MEMO``, ``CHECKNUM`` / ``REFNUM`` (reference) and ``FITID``. A line whose date or amount can't
  be read is kept with its problem.
"""

from __future__ import annotations

import codecs
import datetime as dt
import html
import re
from dataclasses import dataclass, field
from decimal import Decimal

from . import errors
from .errors import LineProblem, StatementError
from .layout import AmountError, RawLine, clean_text, parse_amount
from .source import ParsedStatement

_TAG = re.compile(r"<\s*(/?)\s*([A-Za-z0-9_.]+)[^>]*>")
_OFX_START = re.compile(rb"<\s*OFX\s*>", re.IGNORECASE)
_CHARSET = re.compile(rb"CHARSET\s*:\s*([A-Za-z0-9_-]+)", re.IGNORECASE)
_OFX_DATE = re.compile(r"^\s*(\d{4})(\d{2})(\d{2})")
STATEMENTS = ("STMTRS", "CCSTMTRS")
OFX_DATE_FORMAT = "YYYYMMDD"


@dataclass
class Node:
    name: str
    value: str = ""
    children: list[Node] = field(default_factory=list)

    def child(self, name: str) -> Node | None:
        for node in self.children:
            if node.name == name:
                return node
        return None

    def text(self, *path: str) -> str:
        node: Node | None = self
        for name in path:
            node = node.child(name) if node is not None else None
        return node.value if node is not None else ""

    def find_all(self, name: str) -> list[Node]:
        found: list[Node] = []
        stack = [self]
        while stack:
            node = stack.pop()
            if node.name == name:
                found.append(node)
                continue  # statements are not nested in statements
            stack.extend(reversed(node.children))
        return found


def looks_like_ofx(data: bytes) -> bool:
    head = data[:8192]
    return b"OFXHEADER" in head.upper() or _OFX_START.search(head) is not None


def _encoding(header: bytes, body: bytes) -> str:
    """UTF-8 when the bytes are valid UTF-8 (a file that declares ``CHARSET:1252`` but holds UTF-8
    — common — reads right; valid multi-byte UTF-8 is next to impossible in real Windows-1252
    text), else the declared single-byte charset, else Windows-1252."""
    if header.startswith(codecs.BOM_UTF8) or body.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    try:
        body.decode("utf-8")
    except UnicodeDecodeError:
        pass
    else:
        return "utf-8"
    charset = _CHARSET.search(header)
    if charset and charset.group(1).upper() in (b"8859-1", b"ISO-8859-1", b"LATIN1"):
        return "latin_1"
    return "cp1252"


def build_tree(text: str) -> Node:
    """The element tree of an OFX body (SGML or XML; see the module docstring)."""
    root = Node("#root")
    stack = [root]
    matches = list(_TAG.finditer(text))
    for index, match in enumerate(matches):
        closing, name = match.group(1), match.group(2).upper()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        following = text[match.end() : end]
        if closing:
            names = [node.name for node in stack]
            if name in names[1:]:
                while stack[-1].name != name:
                    stack.pop()
                stack.pop()
            continue  # a leaf's closing tag (XML) or a stray one
        value = following.strip()
        if value:  # a leaf: <TRNAMT>-4.25
            stack[-1].children.append(Node(name, html.unescape(value)))
            continue
        if name == "STMTTRN" and stack[-1].name == "STMTTRN":
            stack.pop()  # an unclosed previous transaction
        node = Node(name)
        stack[-1].children.append(node)
        stack.append(node)
    return root


def ofx_date(value: str) -> dt.date | None:
    match = _OFX_DATE.match(value or "")
    if not match:
        return None
    try:
        return dt.date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return None


def _amount(value: str) -> tuple[Decimal | None, bool]:
    text = (value or "").strip()
    if "," in text and "." not in text:
        text = text.replace(",", ".")  # 4,25 (some European exports)
    try:
        return parse_amount(text), True
    except AmountError:
        return None, False


def transaction_line(row: int, node: Node) -> RawLine:
    problems: list[LineProblem] = []
    raw_date = node.text("DTPOSTED") or node.text("DTUSER")
    date = ofx_date(raw_date)
    if not raw_date:
        problems.append(LineProblem(errors.ROW_DATE_MISSING, {"row": row}))
    elif date is None:
        problems.append(
            LineProblem(
                errors.ROW_DATE_FORMAT, {"row": row, "value": raw_date, "format": OFX_DATE_FORMAT}
            )
        )
    raw_amount = node.text("TRNAMT")
    amount, readable = _amount(raw_amount)
    if not readable:
        problems.append(
            LineProblem(errors.ROW_AMOUNT_INVALID, {"row": row, "value": clean_text(raw_amount)})
        )
    elif amount is None:
        problems.append(LineProblem(errors.ROW_AMOUNT_MISSING, {"row": row}))
    name = clean_text(node.text("NAME") or node.text("PAYEE", "NAME"))
    memo = clean_text(node.text("MEMO"))
    description = name if not memo or memo == name else clean_text(f"{name} {memo}")
    return RawLine(
        row=row,
        date=date,
        amount=amount,
        description=description,
        payee=name,
        reference=clean_text(node.text("CHECKNUM") or node.text("REFNUM")),
        fitid=clean_text(node.text("FITID")),
        problems=tuple(problems),
    )


def _account_id(statement: Node) -> str:
    for holder in ("BANKACCTFROM", "CCACCTFROM"):
        account = statement.child(holder)
        if account is not None:
            return account.text("ACCTID")
    return ""


def parse_ofx(data: bytes, filename: str, file_format: str, *, last4: str = "") -> ParsedStatement:
    start = _OFX_START.search(data)
    if start is None:
        raise StatementError(errors.OFX_NO_STATEMENT, name=filename)
    header, body = data[: start.start()], data[start.start() :]
    encoding = _encoding(header, body)
    text = body.decode("utf-8" if encoding == "utf-8-sig" else encoding, errors="replace")
    tree = build_tree(text)
    statements = [s for name in STATEMENTS for s in tree.find_all(name)]
    if not statements:
        raise StatementError(errors.OFX_NO_STATEMENT, name=filename)
    chosen = statements[0]
    warnings: list[str] = []
    if len(statements) > 1:
        if last4:
            chosen = next((s for s in statements if _account_id(s).endswith(last4)), chosen)
        warnings.append(
            str(errors.OFX_SEVERAL_ACCOUNTS.text(count=len(statements), account=_mask(chosen)))
        )
    transactions = chosen.child("BANKTRANLIST")
    nodes = [n for n in (transactions.children if transactions else []) if n.name == "STMTTRN"]
    lines = tuple(transaction_line(row, node) for row, node in enumerate(nodes, start=1))
    return ParsedStatement(
        format=file_format,
        encoding=encoding,
        lines=lines,
        account_id=_account_id(chosen),
        currency=chosen.text("CURDEF"),
        warnings=tuple(warnings),
    )


def _mask(statement: Node) -> str:
    account = _account_id(statement)
    return f"•••• {account[-4:]}" if account else "?"
