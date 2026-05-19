"""RCSB PDB client tests (HTTP fully mocked via respx).

Phase 2 wraps the RCSB REST + Data API endpoints behind
:mod:`pinsilico.db.rcsb_pdb`. The Phase 5 route layer calls this; the
Tauri webview never reaches RCSB directly.

External HTTP is **always** mocked in unit tests per BUILD_PROMPT.md §6;
a nightly job (Phase 12) hits real RCSB with @pytest.mark.live_network.

Locked invariants:

* :func:`fetch_pdb_by_id` returns a :class:`PdbEntry` with the raw PDB
  text in ``pdb_text``.
* Non-200 status from RCSB raises :class:`DbError` with the provider
  slug ``"rcsb"`` and the original status code.
* The query string passes through the user's case (RCSB normalises to
  uppercase, but we should not pre-mangle).
"""

from __future__ import annotations

import httpx
import pytest
import respx
from pinsilico.db.base import DbError, PdbEntry
from pinsilico.db.rcsb_pdb import RCSB_FILES_BASE, fetch_pdb_by_id, search_pdb_by_keyword

_TINY_PDB = """\
HEADER    HIV-1 PROTEASE                          01-JAN-94   1HSG
ATOM      1  N   PRO A   1      28.140  10.140  31.110  1.00 24.61           N
END
"""


class TestFetchPdbById:
    @respx.mock
    def test_returns_pdb_entry_on_200(self) -> None:
        respx.get(f"{RCSB_FILES_BASE}/1HSG.pdb").mock(
            return_value=httpx.Response(200, text=_TINY_PDB),
        )
        entry = fetch_pdb_by_id("1HSG")
        assert isinstance(entry, PdbEntry)
        assert entry.identifier == "1HSG"
        assert entry.pdb_text.startswith("HEADER")
        assert "HIV-1 PROTEASE" in entry.pdb_text

    @respx.mock
    def test_passes_id_uppercase(self) -> None:
        # RCSB ids are case-insensitive but uppercase is conventional.
        route = respx.get(f"{RCSB_FILES_BASE}/1HSG.pdb").mock(
            return_value=httpx.Response(200, text=_TINY_PDB),
        )
        fetch_pdb_by_id("1hsg")
        assert route.called

    @respx.mock
    def test_404_raises_dberror(self) -> None:
        respx.get(f"{RCSB_FILES_BASE}/ZZZZ.pdb").mock(
            return_value=httpx.Response(404, text="Not Found"),
        )
        with pytest.raises(DbError) as exc:
            fetch_pdb_by_id("ZZZZ")
        assert exc.value.provider == "rcsb"
        assert exc.value.status_code == 404

    @respx.mock
    def test_500_raises_dberror(self) -> None:
        respx.get(f"{RCSB_FILES_BASE}/1HSG.pdb").mock(
            return_value=httpx.Response(500, text="Internal Server Error"),
        )
        with pytest.raises(DbError) as exc:
            fetch_pdb_by_id("1HSG")
        assert exc.value.provider == "rcsb"
        assert exc.value.status_code == 500

    @respx.mock
    def test_empty_body_raises_dberror(self) -> None:
        respx.get(f"{RCSB_FILES_BASE}/1HSG.pdb").mock(
            return_value=httpx.Response(200, text=""),
        )
        with pytest.raises(DbError) as exc:
            fetch_pdb_by_id("1HSG")
        assert exc.value.provider == "rcsb"

    @respx.mock
    def test_network_error_raises_dberror(self) -> None:
        respx.get(f"{RCSB_FILES_BASE}/1HSG.pdb").mock(
            side_effect=httpx.ConnectError("simulated network failure"),
        )
        with pytest.raises(DbError) as exc:
            fetch_pdb_by_id("1HSG")
        assert exc.value.provider == "rcsb"


class TestSearchPdbByKeyword:
    @respx.mock
    def test_returns_list_of_ids(self) -> None:
        body = {
            "result_set": [
                {"identifier": "1HSG", "score": 1.0},
                {"identifier": "4HVP", "score": 0.95},
            ],
            "total_count": 2,
        }
        respx.post("https://search.rcsb.org/rcsbsearch/v2/query").mock(
            return_value=httpx.Response(200, json=body),
        )
        ids = search_pdb_by_keyword("HIV protease", limit=10)
        assert ids == ["1HSG", "4HVP"]

    @respx.mock
    def test_empty_result_returns_empty_list(self) -> None:
        respx.post("https://search.rcsb.org/rcsbsearch/v2/query").mock(
            return_value=httpx.Response(204, json=None),
        )
        ids = search_pdb_by_keyword("nothing-matches", limit=10)
        assert ids == []

    @respx.mock
    def test_4xx_raises_dberror(self) -> None:
        respx.post("https://search.rcsb.org/rcsbsearch/v2/query").mock(
            return_value=httpx.Response(400, json={"error": "bad query"}),
        )
        with pytest.raises(DbError) as exc:
            search_pdb_by_keyword("???", limit=10)
        assert exc.value.provider == "rcsb"
        assert exc.value.status_code == 400

    @respx.mock
    def test_limit_passed_in_query(self) -> None:
        route = respx.post("https://search.rcsb.org/rcsbsearch/v2/query").mock(
            return_value=httpx.Response(200, json={"result_set": [], "total_count": 0}),
        )
        search_pdb_by_keyword("HIV", limit=3)
        assert route.called
        request = route.calls.last.request
        body = request.content.decode("utf-8")
        assert '"rows":3' in body or '"rows": 3' in body
