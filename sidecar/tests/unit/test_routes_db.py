"""Tests for /db/* routes.

External HTTP fully mocked via respx; auth gating exercised via the
real TokenVerifier dependency on create_app(token=...).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pinsilico.db.alphafold import ALPHAFOLD_FILES_BASE
from pinsilico.db.chembl import CHEMBL_API_BASE
from pinsilico.db.pubchem import PUBCHEM_REST_BASE
from pinsilico.db.rcsb_pdb import RCSB_FILES_BASE
from pinsilico.db.uniprot import UNIPROT_REST_BASE
from pinsilico.server import create_app

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_TOKEN = "phase5-test-token-1234567890"  # noqa: S105 - fixture, not a credential

_TINY_PDB = """\
HEADER    HIV-1 PROTEASE
ATOM      1  N   PRO A   1      28.140  10.140  31.110  1.00 24.61           N
END
"""

_TINY_FASTA = """\
>sp|P12345|TEST_HUMAN Test
MKAILVVLLY
"""


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(token=_TOKEN)
    with TestClient(app) as c:
        yield c


def _hdr(token: str = _TOKEN) -> dict[str, str]:
    return {"X-Pinsilico-Token": token}


class TestAuthGating:
    def test_rcsb_route_requires_token(self, client: TestClient) -> None:
        r = client.get("/db/rcsb/structures/1HSG")
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "MISSING_TOKEN"

    def test_uniprot_route_requires_token(self, client: TestClient) -> None:
        r = client.get("/db/uniprot/proteins/P12345")
        assert r.status_code == 401


class TestRcsbRoutes:
    @respx.mock
    def test_fetch_pdb_happy(self, client: TestClient) -> None:
        respx.get(f"{RCSB_FILES_BASE}/1HSG.pdb").mock(
            return_value=httpx.Response(200, text=_TINY_PDB),
        )
        r = client.get("/db/rcsb/structures/1HSG", headers=_hdr())
        assert r.status_code == 200
        body = r.json()
        assert body["identifier"] == "1HSG"
        assert "HIV-1 PROTEASE" in body["pdb_text"]

    @respx.mock
    def test_fetch_pdb_upstream_404_becomes_502(self, client: TestClient) -> None:
        respx.get(f"{RCSB_FILES_BASE}/ZZZZ.pdb").mock(
            return_value=httpx.Response(404, text="not found"),
        )
        r = client.get("/db/rcsb/structures/ZZZZ", headers=_hdr())
        assert r.status_code == 502
        body = r.json()
        assert body["error"]["code"] == "DB_ERROR"
        assert body["error"]["details"]["provider"] == "rcsb"
        assert body["error"]["details"]["upstream_status"] == 404

    @respx.mock
    def test_search(self, client: TestClient) -> None:
        respx.post("https://search.rcsb.org/rcsbsearch/v2/query").mock(
            return_value=httpx.Response(
                200,
                json={"result_set": [{"identifier": "1HSG"}], "total_count": 1},
            ),
        )
        r = client.get("/db/rcsb/search?q=HIV+protease&limit=10", headers=_hdr())
        assert r.status_code == 200
        assert r.json()["identifiers"] == ["1HSG"]

    def test_search_missing_q_422(self, client: TestClient) -> None:
        r = client.get("/db/rcsb/search?limit=10", headers=_hdr())
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"


class TestUniProtRoutes:
    @respx.mock
    def test_fetch_happy(self, client: TestClient) -> None:
        respx.get(f"{UNIPROT_REST_BASE}/uniprotkb/P12345.fasta").mock(
            return_value=httpx.Response(200, text=_TINY_FASTA),
        )
        r = client.get("/db/uniprot/proteins/P12345", headers=_hdr())
        assert r.status_code == 200
        body = r.json()
        assert body["accession"] == "P12345"
        assert body["sequence"].startswith("MKAILVVLLY")


class TestAlphaFoldRoute:
    @respx.mock
    def test_fetch_happy(self, client: TestClient) -> None:
        respx.get(f"{ALPHAFOLD_FILES_BASE}/AF-P12345-F1-model_v4.pdb").mock(
            return_value=httpx.Response(200, text=_TINY_PDB),
        )
        r = client.get("/db/alphafold/structures/P12345", headers=_hdr())
        assert r.status_code == 200
        body = r.json()
        assert body["identifier"] == "AF-P12345-F1"


class TestChemblRoutes:
    @respx.mock
    def test_targets(self, client: TestClient) -> None:
        respx.get(f"{CHEMBL_API_BASE}/target/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "targets": [
                        {
                            "target_chembl_id": "CHEMBL150",
                            "pref_name": "HIV-1 protease",
                            "organism": "HIV-1",
                        },
                    ],
                },
            ),
        )
        r = client.get("/db/chembl/targets?q=hiv&limit=5", headers=_hdr())
        assert r.status_code == 200
        assert r.json()[0]["target_chembl_id"] == "CHEMBL150"

    @respx.mock
    def test_compound(self, client: TestClient) -> None:
        respx.get(f"{CHEMBL_API_BASE}/molecule/CHEMBL150").mock(
            return_value=httpx.Response(
                200,
                json={
                    "molecule_chembl_id": "CHEMBL150",
                    "pref_name": "INDINAVIR",
                    "molecule_structures": {"canonical_smiles": "CC(C)(C)N"},
                    "max_phase": 4,
                },
            ),
        )
        r = client.get("/db/chembl/compounds/CHEMBL150", headers=_hdr())
        body = r.json()
        assert body["pref_name"] == "INDINAVIR"
        assert body["max_phase"] == 4


class TestPubChemRoutes:
    @respx.mock
    def test_smiles_to_cid(self, client: TestClient) -> None:
        respx.get(f"{PUBCHEM_REST_BASE}/compound/smiles/CCO/cids/JSON").mock(
            return_value=httpx.Response(200, json={"IdentifierList": {"CID": [702]}}),
        )
        r = client.get("/db/pubchem/by_smiles?smiles=CCO", headers=_hdr())
        assert r.status_code == 200
        assert r.json() == {"smiles": "CCO", "cid": 702}


class TestDrugBankRoutes:
    @pytest.fixture
    def csv_path(self, tmp_path: Path) -> Path:
        csv = tmp_path / "drugbank.csv"
        csv.write_text(
            "drugbank_id,name,smiles,molecular_formula,groups\n"
            "DB00945,Aspirin,CC(=O)O,C9H8O4,approved\n"
        )
        return csv

    def test_lookup_by_id(self, client: TestClient, csv_path: Path) -> None:
        r = client.get(f"/db/drugbank/drugs/DB00945?csv_path={csv_path}", headers=_hdr())
        assert r.status_code == 200
        assert r.json()["name"] == "Aspirin"

    def test_lookup_not_found_becomes_502(self, client: TestClient, csv_path: Path) -> None:
        r = client.get(f"/db/drugbank/drugs/DB99999?csv_path={csv_path}", headers=_hdr())
        assert r.status_code == 502
        assert r.json()["error"]["details"]["provider"] == "drugbank"
