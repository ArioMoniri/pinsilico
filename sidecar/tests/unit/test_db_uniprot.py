"""UniProt client tests (HTTP fully mocked via respx)."""

from __future__ import annotations

import httpx
import pytest
import respx
from pinsilico.db.base import DbError
from pinsilico.db.uniprot import (
    UNIPROT_REST_BASE,
    UniProtEntry,
    fetch_uniprot,
    search_uniprot,
)

_TINY_FASTA = """\
>sp|P12345|TEST_HUMAN Test protein OS=Homo sapiens OX=9606 GN=TEST PE=1 SV=1
MKAILVVLLYTFATANADTLCIGYHANNSTDTVDTVLEKNVTVTHSVNLLEDKHNGKLCK
LRGVAPLHLGKCNIAGWILGNPECESLSTASSWSYIVETSSSDNGTCYPGDFIDYEELRE
"""


class TestFetchUniProt:
    @respx.mock
    def test_returns_entry_on_200(self) -> None:
        respx.get(f"{UNIPROT_REST_BASE}/uniprotkb/P12345.fasta").mock(
            return_value=httpx.Response(200, text=_TINY_FASTA),
        )
        entry = fetch_uniprot("P12345")
        assert isinstance(entry, UniProtEntry)
        assert entry.accession == "P12345"
        assert "MKAILVVLLY" in entry.sequence  # no FASTA header in .sequence
        assert "\n" not in entry.sequence

    @respx.mock
    def test_404_raises_dberror(self) -> None:
        respx.get(f"{UNIPROT_REST_BASE}/uniprotkb/Q99999.fasta").mock(
            return_value=httpx.Response(404, text="Not Found"),
        )
        with pytest.raises(DbError) as exc:
            fetch_uniprot("Q99999")
        assert exc.value.provider == "uniprot"
        assert exc.value.status_code == 404

    @respx.mock
    def test_network_error_raises_dberror(self) -> None:
        respx.get(f"{UNIPROT_REST_BASE}/uniprotkb/P12345.fasta").mock(
            side_effect=httpx.ConnectError("boom"),
        )
        with pytest.raises(DbError) as exc:
            fetch_uniprot("P12345")
        assert exc.value.provider == "uniprot"

    @respx.mock
    def test_empty_body_raises(self) -> None:
        respx.get(f"{UNIPROT_REST_BASE}/uniprotkb/P12345.fasta").mock(
            return_value=httpx.Response(200, text=""),
        )
        with pytest.raises(DbError):
            fetch_uniprot("P12345")

    @respx.mock
    def test_accession_passed_uppercase(self) -> None:
        route = respx.get(f"{UNIPROT_REST_BASE}/uniprotkb/P12345.fasta").mock(
            return_value=httpx.Response(200, text=_TINY_FASTA),
        )
        fetch_uniprot("p12345")
        assert route.called


class TestSearchUniProt:
    @respx.mock
    def test_returns_accession_list(self) -> None:
        body = {
            "results": [
                {"primaryAccession": "P12345", "proteinDescription": {}},
                {"primaryAccession": "Q98765", "proteinDescription": {}},
            ],
        }
        respx.get(f"{UNIPROT_REST_BASE}/uniprotkb/search").mock(
            return_value=httpx.Response(200, json=body),
        )
        accs = search_uniprot("HIV protease", limit=10)
        assert accs == ["P12345", "Q98765"]

    @respx.mock
    def test_empty_results(self) -> None:
        respx.get(f"{UNIPROT_REST_BASE}/uniprotkb/search").mock(
            return_value=httpx.Response(200, json={"results": []}),
        )
        assert search_uniprot("nothing", limit=10) == []

    @respx.mock
    def test_400_raises_dberror(self) -> None:
        respx.get(f"{UNIPROT_REST_BASE}/uniprotkb/search").mock(
            return_value=httpx.Response(400, json={"messages": ["bad"]}),
        )
        with pytest.raises(DbError) as exc:
            search_uniprot("???", limit=10)
        assert exc.value.provider == "uniprot"
        assert exc.value.status_code == 400
