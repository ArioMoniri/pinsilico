"""DrugBank client tests.

DrugBank ships as a bundled CSV (BUILD_PROMPT.md §3) — no HTTP. The
client reads the CSV from a configurable path so Phase 12 packaging
can drop the actual approved-drugs CSV under sidecar/resources/ at
build time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pinsilico.db.base import DbError
from pinsilico.db.drugbank import (
    DrugBankRecord,
    find_drug_by_id,
    find_drug_by_name,
    search_drugs,
)

if TYPE_CHECKING:
    from pathlib import Path


_FIXTURE_CSV = """\
drugbank_id,name,smiles,molecular_formula,groups
DB00945,Aspirin,CC(=O)Oc1ccccc1C(=O)O,C9H8O4,approved
DB01050,Ibuprofen,CC(C)Cc1ccc(C(C)C(=O)O)cc1,C13H18O2,approved
DB00316,Acetaminophen,CC(=O)Nc1ccc(O)cc1,C8H9NO2,approved
DB00264,Metoprolol,CC(C)NCC(O)COc1ccc(CCOC)cc1,C15H25NO3,approved
"""


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    p = tmp_path / "drugbank.csv"
    p.write_text(_FIXTURE_CSV)
    return p


class TestFindDrugById:
    def test_returns_record(self, csv_path: Path) -> None:
        rec = find_drug_by_id("DB00945", csv_path=csv_path)
        assert isinstance(rec, DrugBankRecord)
        assert rec.name == "Aspirin"
        assert rec.smiles == "CC(=O)Oc1ccccc1C(=O)O"
        assert "approved" in rec.groups

    def test_case_insensitive(self, csv_path: Path) -> None:
        rec = find_drug_by_id("db00945", csv_path=csv_path)
        assert rec.name == "Aspirin"

    def test_unknown_id_raises_dberror(self, csv_path: Path) -> None:
        with pytest.raises(DbError) as exc:
            find_drug_by_id("DB99999", csv_path=csv_path)
        assert exc.value.provider == "drugbank"

    def test_missing_csv_raises_dberror(self, tmp_path: Path) -> None:
        with pytest.raises(DbError) as exc:
            find_drug_by_id("DB00945", csv_path=tmp_path / "no_such_file.csv")
        assert exc.value.provider == "drugbank"


class TestFindDrugByName:
    def test_exact_match(self, csv_path: Path) -> None:
        rec = find_drug_by_name("Aspirin", csv_path=csv_path)
        assert rec.drugbank_id == "DB00945"

    def test_case_insensitive(self, csv_path: Path) -> None:
        rec = find_drug_by_name("aspirin", csv_path=csv_path)
        assert rec.drugbank_id == "DB00945"

    def test_unknown_name_raises(self, csv_path: Path) -> None:
        with pytest.raises(DbError):
            find_drug_by_name("Notadrug", csv_path=csv_path)


class TestSearchDrugs:
    def test_keyword_search_substring(self, csv_path: Path) -> None:
        # "pro" matches Metoprolol and others if any
        results = search_drugs("pro", csv_path=csv_path)
        names = {r.name for r in results}
        assert "Metoprolol" in names

    def test_empty_keyword_returns_all(self, csv_path: Path) -> None:
        results = search_drugs("", csv_path=csv_path)
        assert len(results) == 4

    def test_limit_honoured(self, csv_path: Path) -> None:
        results = search_drugs("", csv_path=csv_path, limit=2)
        assert len(results) == 2

    def test_no_matches_returns_empty(self, csv_path: Path) -> None:
        assert search_drugs("zyxwvut", csv_path=csv_path) == []
