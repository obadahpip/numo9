"""Contact import entities (B-03-T03): the fields a contacts file can map to.

``contacts.contact`` — one row per contact (the wide format: details, primary email and phone,
billing and shipping address); ``contacts.person`` — one row per person at a contact (the long
format, unlimited people per contact, B-03-T09), linked by the contact's External ID or number.

The French names are the headers Quebec files commonly use; accents and case don't matter
(``numo9.imports.mapping.normalise``). ``external_id`` and ``number`` are the match keys (B-03-T05:
External ID → contact number → opt-in Business Number; never the name).
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.imports.fields import ImportEntity, ImportField

CONTACT = ImportEntity(
    "contacts.contact",
    _("Contacts"),
    (
        ImportField(
            "external_id",
            _("External ID"),
            ("external reference", "external ref", "legacy id", "old id", "source id"),
            ("identifiant externe", "id externe", "référence externe"),
            match_key=True,
        ),
        ImportField(
            "number",
            _("Contact number"),
            ("contact no", "contact #", "customer number", "client number", "supplier number"),
            ("numéro de contact", "numéro de client", "numéro client", "no de client"),
            match_key=True,
        ),
        ImportField(
            "display_name",
            _("Display name"),
            ("name", "contact name", "company", "company name", "customer name", "business name"),
            (
                "nom",
                "nom affiché",
                "nom du contact",
                "nom du client",
                "entreprise",
                "nom de l'entreprise",
            ),
            required=True,
        ),
        ImportField(
            "legal_name",
            _("Legal name"),
            ("registered name", "legal business name"),
            ("raison sociale", "nom légal", "dénomination sociale"),
        ),
        ImportField(
            "roles", _("Roles"), ("role", "contact type"), ("rôles", "rôle", "type de contact")
        ),
        ImportField(
            "email",
            _("Email"),
            ("e-mail", "email address", "e-mail address", "primary email"),
            ("courriel", "adresse courriel", "adresse électronique", "courrier électronique"),
        ),
        ImportField(
            "phone",
            _("Phone"),
            ("telephone", "phone number", "tel"),
            ("téléphone", "tél", "numéro de téléphone"),
        ),
        ImportField(
            "bn",
            _("Business Number (BN)"),
            ("bn", "business number", "cra business number", "bn9"),
            ("ne", "numéro d'entreprise", "numéro d'entreprise de l'arc"),
        ),
        ImportField(
            "tax_id",
            _("Tax ID"),
            ("tax number", "vat number", "tax registration number"),
            ("numéro fiscal", "numéro de taxe"),
        ),
        ImportField("currency", _("Currency"), ("currency code",), ("devise", "monnaie")),
        ImportField("credit_limit", _("Credit limit"), (), ("limite de crédit",)),
        ImportField(
            "credit_mode",
            _("Credit limit action"),
            ("credit mode",),
            ("mode de crédit", "action limite de crédit"),
        ),
        ImportField("language", _("Language"), ("document language",), ("langue",)),
        ImportField(
            "statement_pref",
            _("Statement preference"),
            ("statements", "statement delivery"),
            ("relevés", "préférence de relevé"),
        ),
        ImportField("t4a_flag", _("T4A slips"), ("t4a", "withholding"), ("feuillets t4a",)),
        ImportField(
            "billing_line1",
            _("Billing address"),
            ("address", "street", "street address", "address line 1", "billing address line 1"),
            ("adresse", "adresse de facturation", "rue", "adresse ligne 1"),
        ),
        ImportField(
            "billing_line2",
            _("Billing address line 2"),
            ("address line 2", "suite", "unit"),
            ("adresse ligne 2", "complément d'adresse"),
        ),
        ImportField("billing_city", _("Billing city"), ("city", "town"), ("ville", "municipalité")),
        ImportField(
            "billing_province",
            _("Billing province"),
            ("province", "province/state", "state", "region", "prov"),
            ("province de facturation",),
        ),
        ImportField(
            "billing_postal_code",
            _("Billing postal code"),
            ("postal code", "postcode", "zip", "zip code"),
            ("code postal", "code postal de facturation"),
        ),
        ImportField("billing_country", _("Billing country"), ("country",), ("pays",)),
        ImportField(
            "shipping_line1",
            _("Shipping address"),
            ("delivery address", "shipping address line 1"),
            ("adresse de livraison",),
        ),
        ImportField(
            "shipping_line2",
            _("Shipping address line 2"),
            ("delivery address line 2",),
            ("adresse de livraison ligne 2",),
        ),
        ImportField(
            "shipping_city", _("Shipping city"), ("delivery city",), ("ville de livraison",)
        ),
        ImportField(
            "shipping_province",
            _("Shipping province"),
            ("delivery province",),
            ("province de livraison",),
        ),
        ImportField(
            "shipping_postal_code",
            _("Shipping postal code"),
            ("delivery postal code",),
            ("code postal de livraison",),
        ),
        ImportField(
            "shipping_country", _("Shipping country"), ("delivery country",), ("pays de livraison",)
        ),
    ),
)

PERSON = ImportEntity(
    "contacts.person",
    _("People at contacts"),
    (
        ImportField(
            "contact_ref",
            _("Contact (External ID or number)"),
            ("contact", "contact ref", "contact reference", "contact number", "external id"),
            ("contact", "référence du contact", "numéro de contact", "identifiant externe"),
            required=True,
            match_key=True,
        ),
        ImportField("first_name", _("First name"), ("given name", "first"), ("prénom",)),
        ImportField(
            "last_name",
            _("Last name"),
            ("surname", "family name", "last"),
            ("nom de famille", "nom"),
        ),
        ImportField(
            "email",
            _("Email"),
            ("e-mail", "email address"),
            ("courriel", "adresse courriel", "adresse électronique"),
        ),
        ImportField(
            "phone", _("Phone"), ("telephone", "phone number", "tel"), ("téléphone", "tél")
        ),
        ImportField(
            "job_title",
            _("Job title"),
            ("title", "position", "role"),
            ("titre", "poste", "fonction"),
        ),
        ImportField(
            "is_primary",
            _("Primary person"),
            ("primary", "main contact"),
            ("principal", "personne principale"),
        ),
        ImportField(
            "include_in_emails",
            _("Include in emails"),
            ("cc on emails", "copy on emails"),
            ("inclure dans les courriels",),
        ),
    ),
)
