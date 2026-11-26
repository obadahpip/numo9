"""Tax-coding rules (K-09-T09, T15): Exempt on accounts normally taxable for a registrant, and
the share of lines overriding their account's default tax code (TAX_CODE_OVERRIDE_RATE).

**EXEMPT_ON_TAXABLE_ACCOUNT** — for a **registrant** (a GST/HST or QST registration that isn't
closed), a posted line on an expense account that is normally taxable (operating expense or cost
of sales, not listed in ``exclude_accounts``) coded with an **Exempt** code (the organisation's
codes of type Exempt). The teardown's every line was "Tax Exempt (0 %)": input tax credits
missed. The fix is a **recode** through find & recode (C-07): the prefilled search (journal
number, account, the exempt code) and the suggested code — the account's own default when it
is taxable, else the purchase standard code of the organisation's province.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from numo9.ledger.models import AccountSubtype, AccountType, JournalLine, JournalStatus

from ..models import ExceptionFinding, Severity
from .base import Context, FixProposal, Hit, Param, Rule, register
from .common import Numbers

LINE = "ledger.JournalLine"
#: Expense sub-types normally taxable on purchase (amortization and income tax never are).
TAXABLE_SUBTYPES = (AccountSubtype.OPERATING_EXPENSE, AccountSubtype.COST_OF_SALES)
DEFAULT_EXEMPT = frozenset({"purchase.exempt", "sales.exempt"})
FILING = ("rt", "qst")


def is_registrant(organisation: Any) -> bool:
    from numo9.orgsettings.models import RegistrationStatus, TaxRegistration

    return (
        TaxRegistration.objects.filter(organisation=organisation, type__in=FILING)
        .exclude(status=RegistrationStatus.CLOSED)
        .exists()
    )


def exempt_codes() -> frozenset[str]:
    from numo9.tax.models import TaxCode, TaxCodeType

    keys = TaxCode.objects.filter(type=TaxCodeType.EXEMPT).values_list("code", flat=True)
    return DEFAULT_EXEMPT | frozenset(keys)


def line_id(line: JournalLine) -> str:
    return f"{line.entry.public_id}:{line.line_no}"


@register
class ExemptOnTaxableAccount(Rule):
    code = "EXEMPT_ON_TAXABLE_ACCOUNT"
    name = gettext_lazy("Exempt code on a normally taxable account")
    description = gettext_lazy(
        "A registrant coded a purchase on a normally taxable expense account as exempt: the "
        "input tax credit may be missed."
    )
    explanation = gettext_lazy(
        "%(journal)s line %(line)s: %(amount)s on %(account)s is coded %(tax_code)s. This account "
        "is normally taxable and the organisation is registered for GST/HST: check the receipt "
        "and claim the input tax credit if tax was paid."
    )
    default_severity = Severity.WARNING
    incremental = True
    has_fix = True
    money_keys = ("amount",)
    params = {"exclude_accounts": Param("codes", [], gettext_lazy("Accounts to leave out"))}

    def covers(self, ctx: Context, finding: ExceptionFinding) -> bool:
        if ctx.scope is None:
            return True
        return finding.subject_id.split(":")[0] in ctx.scope.entries

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        if not is_registrant(ctx.organisation):
            return
        lines = (
            JournalLine.objects.filter(
                entry__status=JournalStatus.POSTED,
                entry__reversal_of__isnull=True,
                account__type=AccountType.EXPENSE,
                account__subtype__in=TAXABLE_SUBTYPES,
                tax_code__in=sorted(exempt_codes()),
            )
            .exclude(account__code__in=ctx.params["exclude_accounts"])
            .select_related("entry", "account")
            .order_by("entry__date", "entry_id", "line_no")
        )
        if ctx.scope is not None:
            lines = lines.filter(entry__public_id__in=sorted(ctx.scope.entries))
        numbers = Numbers(ctx.organisation)
        for line in lines:
            journal = numbers.label(line.entry)
            amount = line.debit - line.credit
            yield Hit(
                LINE,
                line_id(line),
                f"{journal} · {line.line_no}",
                amount,
                {
                    "journal": journal,
                    "entry": str(line.entry.public_id),
                    "number": line.entry.number,
                    "line": line.line_no,
                    "date": line.entry.date.isoformat(),
                    "account": str(line.account),
                    "account_id": str(line.account.public_id),
                    "amount": f"{amount:.2f}",
                    "tax_code": line.tax_code,
                },
            )

    def suggested_code(self, account: Any, exempt: frozenset[str]) -> str:
        from numo9.tax.defaults import home_province

        key = account.default_tax_key or ""
        if key.startswith("purchase.") and key not in exempt:
            return str(key)
        province = home_province(account.organisation)
        return f"purchase.{province}.standard" if province else ""

    def propose_fix(self, finding: ExceptionFinding, ctx: Context) -> FixProposal | None:
        from numo9.ledger.models import Account

        details = finding.details or {}
        account = Account.objects.filter(public_id=details.get("account_id")).first()
        if account is None:
            return None
        suggested = self.suggested_code(account, exempt_codes())
        criteria = {
            "match": "all",
            "conditions": [
                {"field": "number", "op": "is", "value": details.get("number")},
                {"field": "account", "op": "is", "value": str(account.public_id)},
                {"field": "tax_code", "op": "is", "value": details.get("tax_code")},
            ],
        }
        reasoning = _(
            "Recode the tax of %(journal)s line %(line)s from %(from)s to %(to)s with Find & "
            "recode: the journal is reversed and re-posted with the new code (undo is "
            "available), and the input tax credit is calculated."
        ) % {
            "journal": details.get("journal", ""),
            "line": details.get("line", ""),
            "from": details.get("tax_code", ""),
            "to": suggested or _("the right purchase code"),
        }
        return FixProposal(
            "recode",
            reasoning,
            recode={"criteria": criteria, "changes": {"tax_code": suggested} if suggested else {}},
        )


@register
class TaxCodeOverrideRate(Rule):
    """Over the last ``lookback_days``, the share of posted lines whose tax code differs from
    their account's default is above ``threshold_pct`` (at least ``min_lines`` coded lines on
    accounts with a default): defaults that don't fit, or codes picked by hand too often."""

    code = "TAX_CODE_OVERRIDE_RATE"
    name = gettext_lazy("Tax codes often changed from the account default")
    description = gettext_lazy(
        "Many lines use another tax code than their account's default: the defaults may be wrong."
    )
    explanation = gettext_lazy(
        "%(overrides)s of %(lines)s lines in the last %(days)s days (%(pct)s %%) use another tax "
        "code than their account's default (most on %(top)s). Review the accounts' default codes."
    )
    default_severity = Severity.INFO
    params = {
        "threshold_pct": Param(
            "decimal", Decimal("20.00"), gettext_lazy("Share above (%)"), minimum=Decimal("0")
        ),
        "min_lines": Param("int", 20, gettext_lazy("Minimum lines"), minimum=1, maximum=100000),
        "lookback_days": Param("int", 90, gettext_lazy("Days back"), minimum=1, maximum=730),
    }

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        import datetime as dt

        from django.db.models import Count, F

        since = ctx.today - dt.timedelta(days=ctx.params["lookback_days"])
        lines = (
            JournalLine.objects.filter(
                entry__status=JournalStatus.POSTED,
                entry__reversal_of__isnull=True,
                entry__date__gte=since,
            )
            .exclude(account__default_tax_key="")
            .exclude(tax_code="")
        )
        total = lines.count()
        if total < ctx.params["min_lines"]:
            return
        overridden = lines.exclude(tax_code=F("account__default_tax_key"))
        count = overridden.count()
        pct = (Decimal(count) * 100 / Decimal(total)).quantize(Decimal("0.1"))
        if pct <= ctx.params["threshold_pct"]:
            return
        top = list(
            overridden.values("account__code")
            .annotate(n=Count("id"))
            .order_by("-n", "account__code")[:3]
        )
        organisation = ctx.organisation
        yield Hit(
            "tenancy.Organisation",
            str(organisation.public_id),
            organisation.name,
            None,
            {
                "lines": total,
                "overrides": count,
                "pct": f"{pct}",
                "days": ctx.params["lookback_days"],
                "top": ", ".join(row["account__code"] for row in top),
                "accounts": [{"code": r["account__code"], "lines": r["n"]} for r in top],
            },
        )
