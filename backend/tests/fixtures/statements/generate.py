"""Statement import fixtures (F-02-T04): regenerates the files and ``expected.json``.

    python tests/fixtures/statements/generate.py

Five files per format — OFX, QFX, QBO, CSV and XLSX — modelled on what Canadian banks export
(RBC, TD, National Bank, BMO, Tangerine, Scotiabank, Desjardins…), each with the quirks the
parsers must survive: Windows-1252 and UTF-8 with a byte-order mark, French accents, ``;``
delimiters and decimal commas, title rows, headerless files, quoted cells with commas and line
breaks, hidden worksheets, SGML without closing tags, entities, Intuit headers, two accounts in
one file, an empty transaction list. ``expected.json`` holds, per file, the format and the lines
the parser must produce (and, for CSV / XLSX, the layout that reads them).
"""

from __future__ import annotations

import codecs
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
EXPECTED: dict[str, Any] = {}


def line(
    row: int,
    date: str,
    amount: str,
    description: str = "",
    payee: str = "",
    reference: str = "",
    fitid: str = "",
    problems: tuple[str, ...] = (),
    balance: str | None = None,
) -> dict[str, Any]:
    return {
        "row": row,
        "date": date,
        "amount": amount,
        "description": description,
        "payee": payee,
        "reference": reference,
        "fitid": fitid,
        "balance": balance,
        "problems": list(problems),
    }


def write(name: str, data: bytes, expected: dict[str, Any]) -> None:
    (HERE / name).write_bytes(data)
    EXPECTED[name] = expected


# ---- OFX family --------------------------------------------------------------------------------

SGML_HEADER = (
    "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\n"
    "CHARSET:{charset}\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
)
XML_HEADER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    '<?OFX OFXHEADER="200" VERSION="220" SECURITY="NONE" OLDFILEUID="NONE" NEWFILEUID="NONE"?>\n'
)


def signon(intuit: bool = False) -> str:
    bid = "<INTU.BID>00012\n<INTU.USERID>numo9demo\n" if intuit else ""
    return (
        "<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS>\n"
        "<DTSERVER>20260701120000<LANGUAGE>ENG\n" + bid + "</SONRS></SIGNONMSGSRSV1>\n"
    )


def xml_signon(intuit: bool = False) -> str:
    bid = "<INTU.BID>00012</INTU.BID>" if intuit else ""
    return (
        "<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>"
        f"<DTSERVER>20260701120000</DTSERVER><LANGUAGE>ENG</LANGUAGE>{bid}</SONRS>"
        "</SIGNONMSGSRSV1>\n"
    )


def sgml_trn(fields: dict[str, str], close: bool = True) -> str:
    body = "".join(f"<{k}>{v}\n" for k, v in fields.items())
    return "<STMTTRN>\n" + body + ("</STMTTRN>\n" if close else "")


def xml_trn(fields: dict[str, str]) -> str:
    body = "".join(f"<{k}>{v}</{k}>" for k, v in fields.items())
    return f"<STMTTRN>{body}</STMTTRN>\n"


def sgml_bank(trns: str, acct: str = "5678901", balance: str = "1245.75", cc: bool = False) -> str:
    if cc:
        return (
            "<CREDITCARDMSGSRSV1><CCSTMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>\n"
            f"<CCSTMTRS><CURDEF>CAD<CCACCTFROM><ACCTID>{acct}</CCACCTFROM>\n"
            "<BANKTRANLIST><DTSTART>20260601<DTEND>20260630\n" + trns + "</BANKTRANLIST>\n"
            f"<LEDGERBAL><BALAMT>{balance}<DTASOF>20260630</LEDGERBAL>\n"
            "</CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1>\n"
        )
    return (
        "<STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>\n"
        "<STMTRS><CURDEF>CAD<BANKACCTFROM><BANKID>003<BRANCHID>01234"
        f"<ACCTID>{acct}<ACCTTYPE>CHECKING</BANKACCTFROM>\n"
        "<BANKTRANLIST><DTSTART>20260601<DTEND>20260630\n" + trns + "</BANKTRANLIST>\n"
        f"<LEDGERBAL><BALAMT>{balance}<DTASOF>20260630</LEDGERBAL>\n"
        f"<AVAILBAL><BALAMT>{balance}<DTASOF>20260630</AVAILBAL>\n"
        "</STMTRS></STMTTRNRS>\n"
    )


def sgml_file(body: str, charset: str = "1252", intuit: bool = False) -> str:
    return SGML_HEADER.format(charset=charset) + "<OFX>\n" + signon(intuit) + body + "</OFX>\n"


def bank_wrap(statements: str) -> str:
    return "<BANKMSGSRSV1>\n" + statements + "</BANKMSGSRSV1>\n"


def xml_file(trns: str, acct: str = "5678901", cc: bool = False, intuit: bool = False) -> str:
    if cc:
        stmt = (
            "<CREDITCARDMSGSRSV1><CCSTMTTRNRS><TRNUID>1</TRNUID><STATUS><CODE>0</CODE>"
            "<SEVERITY>INFO</SEVERITY></STATUS><CCSTMTRS><CURDEF>CAD</CURDEF><CCACCTFROM>"
            f"<ACCTID>{acct}</ACCTID></CCACCTFROM><BANKTRANLIST><DTSTART>20260601</DTSTART>"
            "<DTEND>20260630</DTEND>\n" + trns + "</BANKTRANLIST><LEDGERBAL><BALAMT>-512.30"
            "</BALAMT><DTASOF>20260630</DTASOF></LEDGERBAL></CCSTMTRS></CCSTMTTRNRS>"
            "</CREDITCARDMSGSRSV1>\n"
        )
    else:
        stmt = (
            "<BANKMSGSRSV1><STMTTRNRS><TRNUID>1</TRNUID><STATUS><CODE>0</CODE>"
            "<SEVERITY>INFO</SEVERITY></STATUS><STMTRS><CURDEF>CAD</CURDEF><BANKACCTFROM>"
            "<BANKID>006</BANKID>"
            f"<ACCTID>{acct}</ACCTID><ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>"
            "<BANKTRANLIST><DTSTART>20260601</DTSTART><DTEND>20260630</DTEND>\n" + trns + ""
            "</BANKTRANLIST><LEDGERBAL><BALAMT>3658.62</BALAMT><DTASOF>20260630</DTASOF>"
            "</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1>\n"
        )
    return XML_HEADER + "<OFX>\n" + xml_signon(intuit) + stmt + "</OFX>\n"


def trn(kind: str, date: str, amount: str, fitid: str, name: str, memo: str = "") -> dict[str, str]:
    fields = {"TRNTYPE": kind, "DTPOSTED": date, "TRNAMT": amount, "FITID": fitid, "NAME": name}
    if memo:
        fields["MEMO"] = memo
    return fields


COFFEE = trn("DEBIT", "20260603", "-4.25", "202606030001", "TIM HORTONS #1234")
COFFEE_2 = trn("DEBIT", "20260603", "-4.25", "202606030002", "TIM HORTONS #1234")
PAY = trn("CREDIT", "20260605", "2500.00", "202606050001", "PAYROLL ACME INC", "Direct deposit")
HYDRO = trn("DEBIT", "20260615", "-132.48", "202606150001", "HYDRO ONE", "Bill payment")


def ofx_line(row: int, fields: dict[str, str], **extra: Any) -> dict[str, Any]:
    date = fields.get("DTPOSTED") or fields.get("DTUSER") or ""
    name, memo = fields.get("NAME", ""), fields.get("MEMO", "")
    return line(
        row,
        f"{date[:4]}-{date[4:6]}-{date[6:8]}",
        fields["TRNAMT"] if "." in fields["TRNAMT"] else fields["TRNAMT"] + ".00",
        description=extra.pop("description", f"{name} {memo}".strip()),
        payee=extra.pop("payee", name),
        fitid=fields.get("FITID", ""),
        **extra,
    )


def ofx_fixtures() -> None:
    # 1. SGML 1.02, Windows-1252 accents
    cafe = trn("DEBIT", "20260604", "-12.50", "202606040001", "CAFÉ DÉPÔT MONTRÉAL")
    body = sgml_trn(COFFEE) + sgml_trn(cafe) + sgml_trn(PAY)
    write(
        "sgml_chequing_cp1252.ofx",
        sgml_file(bank_wrap(sgml_bank(body))).encode("cp1252"),
        {
            "format": "ofx",
            "encoding": "cp1252",
            "lines": [ofx_line(1, COFFEE), ofx_line(2, cafe), ofx_line(3, PAY)],
        },
    )
    # 2. OFX 2.2 XML, UTF-8
    grocery = trn("POS", "20260612", "-87.13", "X3", "ÉPICERIE MÉTRO", "Carte 1234")
    trns = xml_trn(PAY) + xml_trn(grocery)
    write(
        "xml_v220.ofx",
        xml_file(trns).encode("utf-8"),
        {
            "format": "ofx",
            "encoding": "utf-8",
            "lines": [ofx_line(1, PAY), ofx_line(2, grocery)],
        },
    )
    # 3. Credit card statement: purchases negative, payment positive
    amazon = trn("DEBIT", "20260608", "-9.99", "CC1", "AMAZON.CA")
    payment = trn("CREDIT", "20260620", "500.00", "CC2", "PAYMENT - THANK YOU")
    write(
        "creditcard.ofx",
        sgml_file(
            sgml_bank(sgml_trn(amazon) + sgml_trn(payment), acct="4510XXXXXXXX9012", cc=True)
        ).encode("ascii"),
        {
            "format": "ofx",
            "encoding": "utf-8",
            "lines": [ofx_line(1, amazon), ofx_line(2, payment)],
        },
    )
    # 4. Sloppy SGML: no </STMTTRN>, lower-case tags, a date with time and time zone
    sloppy = {**COFFEE, "DTPOSTED": "20260603120000.000[-5:EST]"}
    atm = trn("ATM", "20260611", "-60.00", "ATM1", "ATM WITHDRAWAL")
    lower_tags = re.sub(
        r"<(/?)([A-Z]+)>", lambda m: f"<{m[1]}{m[2].lower()}>", sgml_trn(atm, False)
    )
    body = sgml_trn(sloppy, close=False) + "  " + lower_tags
    write(
        "sloppy_sgml.ofx",
        sgml_file(bank_wrap(sgml_bank(body)), charset="NONE").encode("ascii"),
        {
            "format": "ofx",
            "encoding": "utf-8",
            "lines": [ofx_line(1, sloppy), ofx_line(2, atm)],
        },
    )
    # 5. Entities, cheque number, reference number, PAYEE aggregate, memo = name, bad amount
    cheque = {
        **trn("CHECK", "20260610", "-800.00", "CHQ123", "LANDLORD &amp; CO"),
        "CHECKNUM": "123",
    }
    ref = {
        "TRNTYPE": "XFER",
        "DTPOSTED": "20260618",
        "TRNAMT": "-25.00",
        "FITID": "REF1",
        "REFNUM": "E-TR-7781",
        "PAYEE": "",
        "NAME": "J. SMITH",
        "MEMO": "J. SMITH",
    }
    bad = trn("DEBIT", "20260619", "abc", "BAD1", "BROKEN LINE")
    body = (
        sgml_trn(cheque)
        + "<STMTTRN>\n<TRNTYPE>XFER\n<DTPOSTED>20260618\n<TRNAMT>-25.00\n<FITID>REF1\n"
        "<REFNUM>E-TR-7781\n<PAYEE>\n<NAME>J. SMITH\n</PAYEE>\n<MEMO>J. SMITH\n</STMTTRN>\n"
        + sgml_trn(bad)
    )
    write(
        "entities_checknum.ofx",
        sgml_file(bank_wrap(sgml_bank(body))).encode("ascii"),
        {
            "format": "ofx",
            "encoding": "utf-8",
            "lines": [
                ofx_line(
                    1,
                    cheque,
                    description="LANDLORD & CO",
                    payee="LANDLORD & CO",
                    reference="123",
                ),
                ofx_line(2, ref, description="J. SMITH", payee="J. SMITH", reference="E-TR-7781"),
                {
                    **line(3, "2026-06-19", "", "BROKEN LINE", "BROKEN LINE", fitid="BAD1"),
                    "amount": None,
                    "problems": ["banking.statement.row.amount_invalid"],
                },
            ],
        },
    )


def qfx_fixtures() -> None:
    # 1. TD web banking QFX (Intuit sign-on elements)
    body = sgml_trn(COFFEE) + sgml_trn(COFFEE_2) + sgml_trn(PAY)
    write(
        "td_web.qfx",
        sgml_file(bank_wrap(sgml_bank(body)), intuit=True).encode("ascii"),
        {
            "format": "qfx",
            "encoding": "utf-8",
            "lines": [ofx_line(1, COFFEE), ofx_line(2, COFFEE_2), ofx_line(3, PAY)],
        },
    )
    # 2. Only DTUSER (no DTPOSTED)
    user = {
        "TRNTYPE": "DEBIT",
        "DTUSER": "20260607",
        "TRNAMT": "-15.00",
        "FITID": "U1",
        "NAME": "PRESTO",
    }
    write(
        "rbc_dtuser.qfx",
        sgml_file(bank_wrap(sgml_bank(sgml_trn(user) + sgml_trn(HYDRO))), intuit=True).encode(
            "ascii"
        ),
        {"format": "qfx", "encoding": "utf-8", "lines": [ofx_line(1, user), ofx_line(2, HYDRO)]},
    )
    # 3. Visa QFX
    gas = trn("DEBIT", "20260609", "-61.20", "V1", "PETRO-CANADA")
    write(
        "cc_visa.qfx",
        sgml_file(sgml_bank(sgml_trn(gas), acct="4510XXXXXXXX9012", cc=True), intuit=True).encode(
            "ascii"
        ),
        {"format": "qfx", "encoding": "utf-8", "lines": [ofx_line(1, gas)]},
    )
    # 4. XML QFX
    write(
        "xml.qfx",
        xml_file(xml_trn(HYDRO) + xml_trn(PAY), intuit=True).encode("utf-8"),
        {"format": "qfx", "encoding": "utf-8", "lines": [ofx_line(1, HYDRO), ofx_line(2, PAY)]},
    )
    # 5. Two accounts in one file: the first is read, with a warning
    first = sgml_bank(sgml_trn(COFFEE), acct="5678901")
    second = sgml_bank(sgml_trn(PAY) + sgml_trn(HYDRO), acct="9990004321")
    write(
        "two_accounts.qfx",
        sgml_file(bank_wrap(first + second), intuit=True).encode("ascii"),
        {
            "format": "qfx",
            "encoding": "utf-8",
            "warnings": 1,
            "lines": [ofx_line(1, COFFEE)],
            "last4": {"4321": [ofx_line(1, PAY), ofx_line(2, HYDRO)]},
        },
    )


def qbo_fixtures() -> None:
    # 1. Intuit header: BOM and blank lines before OFXHEADER
    write(
        "intuit_header.qbo",
        codecs.BOM_UTF8
        + b"\r\n\r\n"
        + sgml_file(bank_wrap(sgml_bank(sgml_trn(COFFEE) + sgml_trn(PAY))), intuit=True).encode(
            "ascii"
        ),
        {
            "format": "qbo",
            "encoding": "utf-8-sig",
            "lines": [ofx_line(1, COFFEE), ofx_line(2, PAY)],
        },
    )
    # 2. CRLF line endings
    write(
        "crlf.qbo",
        sgml_file(bank_wrap(sgml_bank(sgml_trn(HYDRO))), intuit=True)
        .replace("\n", "\r\n")
        .encode("ascii"),
        {"format": "qbo", "encoding": "utf-8", "lines": [ofx_line(1, HYDRO)]},
    )
    # 3. XML QBO with an accent
    resto = trn("POS", "20260614", "-42.00", "R1", "RESTAURANT L’ÉRABLE")
    write(
        "xml.qbo",
        xml_file(xml_trn(resto), intuit=True).encode("utf-8"),
        {"format": "qbo", "encoding": "utf-8", "lines": [ofx_line(1, resto)]},
    )
    # 4. A statement with no transactions
    write(
        "empty_list.qbo",
        sgml_file(bank_wrap(sgml_bank("")), intuit=True).encode("ascii"),
        {"format": "qbo", "encoding": "utf-8", "lines": []},
    )
    # 5. Credit card, unclosed transactions, CRLF
    one = trn("DEBIT", "20260602", "-19.99", "Q1", "NETFLIX.COM")
    two = trn("CREDIT", "20260625", "19.99", "Q2", "NETFLIX.COM REFUND")
    write(
        "credit_card.qbo",
        sgml_file(
            sgml_bank(sgml_trn(one, close=False) + sgml_trn(two, close=False), cc=True),
            intuit=True,
        )
        .replace("\n", "\r\n")
        .encode("ascii"),
        {"format": "qbo", "encoding": "utf-8", "lines": [ofx_line(1, one), ofx_line(2, two)]},
    )


# ---- CSV ---------------------------------------------------------------------------------------


def csv_fixtures() -> None:
    write(
        "rbc_chequing.csv",
        (
            b'"Account Type","Account Number","Transaction Date","Cheque Number",'
            b'"Description 1","Description 2","CAD$","USD$"\n'
            b'Chequing,01234-5678901,6/3/2026,,"Tim Hortons #1234","Toronto ON",-4.25,\n'
            b'Chequing,01234-5678901,6/3/2026,,"Tim Hortons #1234","Toronto ON",-4.25,\n'
            b'Chequing,01234-5678901,6/5/2026,,"PAYROLL DEPOSIT","ACME INC",2500.00,\n'
            b'Chequing,01234-5678901,6/10/2026,123,"CHEQUE","",-800.00,\n'
            b'Chequing,01234-5678901,6/15/2026,,"Hydro One","Bill payment",-132.48,\n'
        ),
        {
            "format": "csv",
            "encoding": "utf-8",
            "delimiter": ",",
            "layout": {
                "columns": [
                    "ignore",
                    "ignore",
                    "date",
                    "reference",
                    "description",
                    "description",
                    "amount",
                    "ignore",
                ],
                "date_format": "MM/DD/YYYY",
            },
            "lines": [
                line(2, "2026-06-03", "-4.25", "Tim Hortons #1234 Toronto ON"),
                line(3, "2026-06-03", "-4.25", "Tim Hortons #1234 Toronto ON"),
                line(4, "2026-06-05", "2500.00", "PAYROLL DEPOSIT ACME INC"),
                line(5, "2026-06-10", "-800.00", "CHEQUE", reference="123"),
                line(6, "2026-06-15", "-132.48", "Hydro One Bill payment"),
            ],
        },
    )
    write(
        "td_chequing.csv",
        (
            b"06/03/2026,TIM HORTONS #1234,4.25,,1245.75\n"
            b"06/05/2026,PAYROLL ACME INC,,2500.00,3745.75\n"
            b"06/10/2026,CHQ#00123,800.00,,2945.75\n"
            b"06/15/2026,HYDRO ONE BPY,132.48,,2813.27\n"
            b'06/20/2026,"E-TRANSFER, J. SMITH",,50.00,2863.27\n'
        ),
        {
            "format": "csv",
            "encoding": "utf-8",
            "delimiter": ",",
            "layout": {
                "columns": ["date", "description", "debit", "credit", "balance"],
                "date_format": "MM/DD/YYYY",
                "sign": "debit_credit",
                "has_header": False,
            },
            "lines": [
                line(1, "2026-06-03", "-4.25", "TIM HORTONS #1234", balance="1245.75"),
                line(2, "2026-06-05", "2500.00", "PAYROLL ACME INC", balance="3745.75"),
                line(3, "2026-06-10", "-800.00", "CHQ#00123", balance="2945.75"),
                line(4, "2026-06-15", "-132.48", "HYDRO ONE BPY", balance="2813.27"),
                line(5, "2026-06-20", "50.00", "E-TRANSFER, J. SMITH", balance="2863.27"),
            ],
        },
    )
    write(
        "national_bank_fr_cp1252.csv",
        (
            "Date;Description;Catégorie;Débit;Crédit;Solde\r\n"
            "2026-06-03;Café Dépôt Montréal;Restaurants;4,25;;1 245,75\r\n"
            "2026-06-05;Dépôt de paie;Revenus;;2 500,00;3 745,75\r\n"
            "2026-06-12;Épicerie Métro;Épicerie;87,13;;3 658,62\r\n"
        ).encode("cp1252"),
        {
            "format": "csv",
            "encoding": "cp1252",
            "delimiter": ";",
            "layout": {
                "columns": ["date", "description", "ignore", "debit", "credit", "balance"],
                "sign": "debit_credit",
                "decimal_separator": ",",
            },
            "lines": [
                line(2, "2026-06-03", "-4.25", "Café Dépôt Montréal", balance="1245.75"),
                line(3, "2026-06-05", "2500.00", "Dépôt de paie", balance="3745.75"),
                line(4, "2026-06-12", "-87.13", "Épicerie Métro", balance="3658.62"),
            ],
        },
    )
    write(
        "bmo_preamble_bom.csv",
        codecs.BOM_UTF8
        + (
            b"Following data is valid as of 20260630201500 (Year/Month/Day/Hour/Minute/Second)\n"
            b"\n"
            b"First Bank Card,Transaction Type,Date Posted, Transaction Amount,Description\n"
            b"'5191230000001234',DEBIT,20260603,-4.25,[DN]TIM HORTONS #1234\n"
            b"'5191230000001234',CREDIT,20260605,2500.00,[DP]PAYROLL ACME\n"
            b"'5191230000001234',DEBIT,20260611,-60.00,[CW]ATM WITHDRAWAL\n"
        ),
        {
            "format": "csv",
            "encoding": "utf-8-sig",
            "delimiter": ",",
            "layout": {
                "columns": ["ignore", "ignore", "date", "amount", "description"],
                "date_format": "YYYYMMDD",
                "skip_rows": 1,
            },
            "lines": [
                line(4, "2026-06-03", "-4.25", "[DN]TIM HORTONS #1234"),
                line(5, "2026-06-05", "2500.00", "[DP]PAYROLL ACME"),
                line(6, "2026-06-11", "-60.00", "[CW]ATM WITHDRAWAL"),
            ],
        },
    )
    write(
        "tangerine_quoted.csv",
        (
            b"Transaction date,Transaction,Name,Memo,Amount\n"
            b'6/3/2026,DEBIT,"Tim Hortons, Toronto","Purchase",-4.25\n'
            b'6/4/2026,OTHER,"Interest Paid","",0.87\n'
            b'6/8/2026,DEBIT,"Amazon.ca ""Prime""","Multi\nline memo",-9.99\n'
            b'6/9/2026,CREDIT,"EFT Deposit from ACME","Payroll",1250.00\n'
            b"13/9/2026,DEBIT,Bad date,,-1.00\n"
        ),
        {
            "format": "csv",
            "encoding": "utf-8",
            "delimiter": ",",
            "layout": {
                "columns": ["date", "ignore", "description", "description", "amount"],
                "date_format": "MM/DD/YYYY",
            },
            "lines": [
                line(2, "2026-06-03", "-4.25", "Tim Hortons, Toronto Purchase"),
                line(3, "2026-06-04", "0.87", "Interest Paid"),
                line(4, "2026-06-08", "-9.99", 'Amazon.ca "Prime" Multi line memo'),
                line(5, "2026-06-09", "1250.00", "EFT Deposit from ACME Payroll"),
                {
                    **line(6, "", "-1.00", "Bad date"),
                    "date": None,
                    "problems": ["banking.statement.row.date_format"],
                },
            ],
        },
    )


# ---- XLSX --------------------------------------------------------------------------------------


def _xlsx(name: str, sheets: list[tuple[str, list[list[Any]], bool]]) -> None:
    from openpyxl import Workbook

    book = Workbook()
    book.remove(book.active)
    for title, rows, hidden in sheets:
        sheet = book.create_sheet(title)
        for row in rows:
            sheet.append(row)
        if hidden:
            sheet.sheet_state = "hidden"
    book.active = next(i for i, (_t, _r, hidden) in enumerate(sheets) if not hidden)
    path = HERE / name
    book.save(path)
    # openpyxl stamps the current time in docProps/core.xml: fix it so the bytes are stable.
    import zipfile

    stamp = "2026-07-01T00:00:00Z"
    with zipfile.ZipFile(path) as archive:
        members = [(i, archive.read(i.filename)) for i in archive.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for info, data in members:
            if info.filename == "docProps/core.xml":
                text = data.decode()
                for tag in ("dcterms:created", "dcterms:modified"):
                    start = text.find(f"<{tag}")
                    end = text.find(f"</{tag}>")
                    if start != -1 and end != -1:
                        open_end = text.find(">", start) + 1
                        text = text[:open_end] + stamp + text[end:]
                data = text.encode()
            info.date_time = (2026, 7, 1, 0, 0, 0)
            archive.writestr(info, data)


def xlsx_fixtures() -> None:
    d = dt.datetime
    rows: list[list[Any]] = [
        ["Date", "Description", "Amount"],
        [d(2026, 6, 3), "TIM HORTONS #1234", -4.25],
        [d(2026, 6, 5), "PAYROLL ACME INC", 2500],
        [d(2026, 6, 15), "HYDRO ONE", -132.48],
    ]
    expected_three = [
        line(2, "2026-06-03", "-4.25", "TIM HORTONS #1234"),
        line(3, "2026-06-05", "2500.00", "PAYROLL ACME INC"),
        line(4, "2026-06-15", "-132.48", "HYDRO ONE"),
    ]
    _xlsx("generic_dates.xlsx", [("Transactions", rows, False)])
    EXPECTED["generic_dates.xlsx"] = {
        "format": "xlsx",
        "layout": {"columns": ["date", "description", "amount"], "date_format": "DD/MM/YYYY"},
        "lines": expected_three,
    }
    _xlsx(
        "scotiabank.xlsx",
        [
            (
                "Statement",
                [
                    [
                        "Date",
                        "Description",
                        "Sub-description",
                        "Status",
                        "Type of Transaction",
                        "Amount",
                    ],
                    ["2026-06-03", "POS PURCHASE", "TIM HORTONS #1234", "posted", "Debit", "-4.25"],
                    ["2026-06-05", "PAYROLL DEP.", "ACME INC", "posted", "Credit", "2,500.00"],
                ],
                False,
            )
        ],
    )
    EXPECTED["scotiabank.xlsx"] = {
        "format": "xlsx",
        "layout": {
            "columns": ["date", "description", "description", "ignore", "ignore", "amount"],
        },
        "lines": [
            line(2, "2026-06-03", "-4.25", "POS PURCHASE TIM HORTONS #1234"),
            line(3, "2026-06-05", "2500.00", "PAYROLL DEP. ACME INC"),
        ],
    }
    _xlsx(
        "title_rows.xlsx",
        [
            (
                "Relevé",
                [
                    ["Relevé de compte — Caisse Desjardins"],
                    ["Période : juin 2026"],
                    [],
                    ["Date", "Libellé", "Retrait", "Dépôt"],
                    [d(2026, 6, 3), "Café Dépôt", 4.25, None],
                    [d(2026, 6, 5), "Paie — Acmé", None, 2500],
                ],
                False,
            )
        ],
    )
    EXPECTED["title_rows.xlsx"] = {
        "format": "xlsx",
        "layout": {
            "columns": ["date", "description", "debit", "credit"],
            "sign": "debit_credit",
            "skip_rows": 2,
        },
        "lines": [
            line(5, "2026-06-03", "-4.25", "Café Dépôt"),
            line(6, "2026-06-05", "2500.00", "Paie — Acmé"),
        ],
    }
    _xlsx(
        "hidden_first_sheet.xlsx",
        [
            ("Notes", [["internal notes, not a statement"], ["x", "y", "z"]], True),
            (
                "Visa",
                [
                    ["Posted", "Merchant", "Charge"],
                    [d(2026, 6, 8), "AMAZON.CA", 9.99],
                    [d(2026, 6, 20), "PAYMENT THANK YOU", -500],
                ],
                False,
            ),
        ],
    )
    EXPECTED["hidden_first_sheet.xlsx"] = {
        "format": "xlsx",
        "layout": {"columns": ["date", "description", "amount"], "sign": "inverted"},
        "lines": [
            line(2, "2026-06-08", "-9.99", "AMAZON.CA"),
            line(3, "2026-06-20", "500.00", "PAYMENT THANK YOU"),
        ],
    }
    _xlsx(
        "text_dates_and_rounding.xlsx",
        [
            (
                "Sheet1",
                [
                    ["Date", "Details", "Amount", "Reference"],
                    ["03/06/2026", "COFFEE", -4.249999, "R-1"],
                    ["05/06/2026", "DEPOSIT", 100, 7781],
                    ["13/25/2026", "BAD DATE", -1, ""],
                ],
                False,
            )
        ],
    )
    EXPECTED["text_dates_and_rounding.xlsx"] = {
        "format": "xlsx",
        "layout": {
            "columns": ["date", "description", "amount", "reference"],
            "date_format": "DD/MM/YYYY",
        },
        "lines": [
            line(2, "2026-06-03", "-4.25", "COFFEE", reference="R-1"),
            line(3, "2026-06-05", "100.00", "DEPOSIT", reference="7781"),
            {
                **line(4, "", "-1.00", "BAD DATE"),
                "date": None,
                "problems": ["banking.statement.row.date_format"],
            },
        ],
    }


if __name__ == "__main__":
    ofx_fixtures()
    qfx_fixtures()
    qbo_fixtures()
    csv_fixtures()
    xlsx_fixtures()
    (HERE / "expected.json").write_text(
        json.dumps(EXPECTED, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"{len(EXPECTED)} fixtures written")
