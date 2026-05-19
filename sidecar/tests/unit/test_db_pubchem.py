"""PubChem client tests (HTTP fully mocked via respx)."""

from __future__ import annotations

import httpx
import pytest
import respx
from pinsilico.db.base import DbError
from pinsilico.db.pubchem import (
    PUBCHEM_REST_BASE,
    PubChemCompound,
    fetch_sdf_by_cid,
    smiles_to_cid,
)


class TestSmilesToCid:
    @respx.mock
    def test_returns_first_cid(self) -> None:
        respx.get(f"{PUBCHEM_REST_BASE}/compound/smiles/CCO/cids/JSON").mock(
            return_value=httpx.Response(200, json={"IdentifierList": {"CID": [702, 5234]}}),
        )
        assert smiles_to_cid("CCO") == 702

    @respx.mock
    def test_empty_list_raises(self) -> None:
        respx.get(f"{PUBCHEM_REST_BASE}/compound/smiles/XYZ/cids/JSON").mock(
            return_value=httpx.Response(200, json={"IdentifierList": {"CID": []}}),
        )
        with pytest.raises(DbError):
            smiles_to_cid("XYZ")

    @respx.mock
    def test_404_raises_dberror(self) -> None:
        respx.get(f"{PUBCHEM_REST_BASE}/compound/smiles/XYZ/cids/JSON").mock(
            return_value=httpx.Response(404, text="not found"),
        )
        with pytest.raises(DbError) as exc:
            smiles_to_cid("XYZ")
        assert exc.value.provider == "pubchem"
        assert exc.value.status_code == 404

    @respx.mock
    def test_network_error(self) -> None:
        respx.get(f"{PUBCHEM_REST_BASE}/compound/smiles/CCO/cids/JSON").mock(
            side_effect=httpx.ConnectError("offline"),
        )
        with pytest.raises(DbError) as exc:
            smiles_to_cid("CCO")
        assert exc.value.provider == "pubchem"


class TestFetchSdfByCid:
    @respx.mock
    def test_returns_compound(self) -> None:
        sdf = "ethanol\n  PubChem\n\n  3  2  0  0  0  0  0  0  0  0999 V2000\n$$$$\n"
        respx.get(f"{PUBCHEM_REST_BASE}/compound/cid/702/SDF").mock(
            return_value=httpx.Response(200, text=sdf),
        )
        compound = fetch_sdf_by_cid(702)
        assert isinstance(compound, PubChemCompound)
        assert compound.cid == 702
        assert "PubChem" in compound.sdf_text

    @respx.mock
    def test_404_raises_dberror(self) -> None:
        respx.get(f"{PUBCHEM_REST_BASE}/compound/cid/99999999/SDF").mock(
            return_value=httpx.Response(404, text="not found"),
        )
        with pytest.raises(DbError) as exc:
            fetch_sdf_by_cid(99999999)
        assert exc.value.provider == "pubchem"
        assert exc.value.status_code == 404

    @respx.mock
    def test_empty_body_raises(self) -> None:
        respx.get(f"{PUBCHEM_REST_BASE}/compound/cid/702/SDF").mock(
            return_value=httpx.Response(200, text=""),
        )
        with pytest.raises(DbError):
            fetch_sdf_by_cid(702)
