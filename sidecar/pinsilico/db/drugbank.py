"""DrugBank client — local CSV lookup, no network.

The CSV ships under ``sidecar/resources/drugbank.csv`` (Phase 12
packaging step). For testing and dev, a small fixture is fine. Schema:

    drugbank_id,name,smiles,molecular_formula,groups

``groups`` is a comma-or-semicolon-separated list (we accept either)
typically containing ``approved``, ``experimental``, ``illicit``, ``withdrawn``.

All lookups are case-insensitive on the search field. Whitespace
around fields is stripped on parse.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from pinsilico.db.base import DbError

_PROVIDER = "drugbank"


@dataclass(frozen=True, slots=True)
class DrugBankRecord:
    """One row from the bundled DrugBank CSV."""

    drugbank_id: str
    name: str
    smiles: str
    molecular_formula: str
    groups: tuple[str, ...]


def _read_csv(csv_path: Path) -> list[DrugBankRecord]:
    if not csv_path.exists():
        raise DbError(
            f"DrugBank CSV not found: {csv_path}",
            provider=_PROVIDER,
        )
    rows: list[DrugBankRecord] = []
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            groups_raw = raw.get("groups") or ""
            groups = tuple(
                g.strip()
                for g in groups_raw.replace(";", ",").split(",")
                if g.strip()
            )
            rows.append(
                DrugBankRecord(
                    drugbank_id=(raw.get("drugbank_id") or "").strip(),
                    name=(raw.get("name") or "").strip(),
                    smiles=(raw.get("smiles") or "").strip(),
                    molecular_formula=(raw.get("molecular_formula") or "").strip(),
                    groups=groups,
                )
            )
    return rows


def find_drug_by_id(drugbank_id: str, *, csv_path: Path) -> DrugBankRecord:
    """Look up a record by exact DrugBank ID (case-insensitive)."""
    target = drugbank_id.upper()
    for rec in _read_csv(csv_path):
        if rec.drugbank_id.upper() == target:
            return rec
    raise DbError(
        f"DrugBank ID not found: {drugbank_id}",
        provider=_PROVIDER,
    )


def find_drug_by_name(name: str, *, csv_path: Path) -> DrugBankRecord:
    """Look up a record by exact name (case-insensitive)."""
    target = name.casefold()
    for rec in _read_csv(csv_path):
        if rec.name.casefold() == target:
            return rec
    raise DbError(
        f"DrugBank name not found: {name!r}",
        provider=_PROVIDER,
    )


def search_drugs(
    keyword: str, *, csv_path: Path, limit: int = 25
) -> list[DrugBankRecord]:
    """Return records whose name contains ``keyword`` (case-insensitive).

    Empty keyword returns all rows up to ``limit``. Matching is plain
    substring — Phase 9 may bolt on more sophisticated search; the CSV
    is small enough (≤ 15 000 approved drugs) that linear scan is fine.
    """
    rows = _read_csv(csv_path)
    if not keyword:
        return rows[:limit]
    needle = keyword.casefold()
    matches = [r for r in rows if needle in r.name.casefold()]
    return matches[:limit]
