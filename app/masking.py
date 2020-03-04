"""Deterministic masking of person-to-person counterparties.

The raw snapshot is never rewritten; masking is applied at import time to the
description stored in the local database. A person-shaped description is replaced
with ``Person <8 hex chars of sha256(normalised original)`` so the same
counterparty stays grouped without showing the real name. The description hash
used elsewhere is computed over the stored (already masked) label, so prepared
CSVs and the local database do not diverge.

Masking is a local, documented privacy convenience, not a claim of certainty: it
can over-mask a small organisation whose name looks like a person, and it can fail
to mask a name that looks merchant-like.
"""

from __future__ import annotations

import hashlib
import re

_TITLES = ("MR ", "MRS ", "MISS ", "MS ", "DR ", "PROF ")
_PERSON_TYPES = {"FPO", "FPI", "TFR", "SO"}

# Generic organisational markers that make a description unlikely to be a lone
# person even inside a person-heavy transaction type (FPO/FPI/TFR/SO).
_ORG_MARKERS = {
    "LTD", "LIMITED", "LLP", "PLC", "INC", "CO", "GROUP", "SERVICES",
    "UNIV", "UNIVERSITY", "COLLEGE", "SCHOOL", "COUNCIL", "GOV", "HMRC",
    "ENERGY", "WATER", "MEDIA", "BANK", "ACCOUNT", "LETTINGS", "REMOVALS",
    "MANAGEMENT", "SOLICITORS", "LEGAL", "LEG", "ACCOUNTANTS", "INSURANCE",
    "INSUR", "LIFE", "ASSUR", "CLUB", "CHARITY", "ASSOCIATION", "TRUST",
    "SOCIETY", "FUND", "PARTNERSHIP", "STORE", "SHOP", "MARKETS", "MART",
    "CAFE", "HOTEL", "TRAVEL", "CREDIT", "TRADING", "EXCHANGE",
}

# Organisations observed in this snapshot whose names otherwise look person-shaped
# and would be over-masked by the content rule above.
_OBSERVED_ORGS = {
    "TAMBA",  # Twins And Multiple Births Association
    "IISL",   # account housekeeping line
}

_TOKEN_RE = re.compile(r"[A-Z0-9][A-Z0-9'./-]*")


def normalize(text: str) -> str:
    return " ".join(text.upper().split())


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(normalize(text))


def _looks_personal(text: str, txn_type: str) -> bool:
    upper = normalize(text)
    if upper.startswith(_TITLES):
        return True
    if txn_type not in _PERSON_TYPES:
        return False
    if any(ch.isdigit() for ch in upper):
        return False
    tokens = _tokens(upper)
    if not tokens or len(tokens) > 4:
        return False
    if any(token in _ORG_MARKERS for token in tokens):
        return False
    if any(token in _OBSERVED_ORGS for token in tokens):
        return False
    return all(re.fullmatch(r"[A-Z][A-Z'./-]*", token) for token in tokens)


def mask_description(description: str, txn_type: str) -> str:
    original = description.strip()
    if not _looks_personal(original, txn_type):
        return original
    digest = hashlib.sha256(normalize(original).encode("utf-8")).hexdigest()
    return f"Person {digest[:8]}"


def desc_hash(description: str) -> str:
    return hashlib.sha256(normalize(description).encode("utf-8")).hexdigest()