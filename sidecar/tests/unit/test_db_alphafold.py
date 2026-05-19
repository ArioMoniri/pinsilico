"""AlphaFold DB client tests (HTTP fully mocked via respx)."""

from __future__ import annotations

import httpx
import pytest
import respx
from pinsilico.db.alphafold import ALPHAFOLD_FILES_BASE, fetch_alphafold_pdb
from pinsilico.db.base import DbError, PdbEntry

_TINY_PDB = """\
HEADER    PREDICTED STRUCTURE                     01-JAN-22   AFP12345
ATOM      1  N   MET A   1       0.000   0.000   0.000  1.00 50.00           N
END
"""


class TestFetchAlphaFoldPdb:
    @respx.mock
    def test_returns_pdb_entry_with_model_v4_url(self) -> None:
        respx.get(f"{ALPHAFOLD_FILES_BASE}/AF-P12345-F1-model_v4.pdb").mock(
            return_value=httpx.Response(200, text=_TINY_PDB),
        )
        entry = fetch_alphafold_pdb("P12345")
        assert isinstance(entry, PdbEntry)
        assert entry.identifier == "AF-P12345-F1"
        assert "PREDICTED STRUCTURE" in entry.pdb_text
        assert entry.resolution_angstrom is None  # predicted, not measured

    @respx.mock
    def test_uppercases_accession(self) -> None:
        route = respx.get(f"{ALPHAFOLD_FILES_BASE}/AF-P12345-F1-model_v4.pdb").mock(
            return_value=httpx.Response(200, text=_TINY_PDB),
        )
        fetch_alphafold_pdb("p12345")
        assert route.called

    @respx.mock
    def test_404_raises_dberror(self) -> None:
        respx.get(f"{ALPHAFOLD_FILES_BASE}/AF-Q99999-F1-model_v4.pdb").mock(
            return_value=httpx.Response(404, text="Not Found"),
        )
        with pytest.raises(DbError) as exc:
            fetch_alphafold_pdb("Q99999")
        assert exc.value.provider == "alphafold"
        assert exc.value.status_code == 404

    @respx.mock
    def test_network_error_raises_dberror(self) -> None:
        respx.get(f"{ALPHAFOLD_FILES_BASE}/AF-P12345-F1-model_v4.pdb").mock(
            side_effect=httpx.ConnectError("simulated"),
        )
        with pytest.raises(DbError) as exc:
            fetch_alphafold_pdb("P12345")
        assert exc.value.provider == "alphafold"

    @respx.mock
    def test_empty_body_raises_dberror(self) -> None:
        respx.get(f"{ALPHAFOLD_FILES_BASE}/AF-P12345-F1-model_v4.pdb").mock(
            return_value=httpx.Response(200, text=""),
        )
        with pytest.raises(DbError):
            fetch_alphafold_pdb("P12345")
