"""ChEMBL client tests (HTTP fully mocked via respx)."""

from __future__ import annotations

import httpx
import pytest
import respx
from pinsilico.db.base import DbError
from pinsilico.db.chembl import (
    CHEMBL_API_BASE,
    ChemblCompound,
    ChemblTarget,
    fetch_activities,
    fetch_compound,
    search_targets,
)


class TestSearchTargets:
    @respx.mock
    def test_returns_target_list(self) -> None:
        body = {
            "targets": [
                {
                    "target_chembl_id": "CHEMBL2095157",
                    "pref_name": "HIV-1 protease",
                    "organism": "Human immunodeficiency virus 1",
                },
                {
                    "target_chembl_id": "CHEMBL262",
                    "pref_name": "Protease",
                    "organism": "Homo sapiens",
                },
            ],
        }
        respx.get(f"{CHEMBL_API_BASE}/target/search").mock(
            return_value=httpx.Response(200, json=body),
        )
        results = search_targets("HIV protease", limit=10)
        assert len(results) == 2
        assert isinstance(results[0], ChemblTarget)
        assert results[0].target_chembl_id == "CHEMBL2095157"
        assert results[0].pref_name == "HIV-1 protease"

    @respx.mock
    def test_empty_results(self) -> None:
        respx.get(f"{CHEMBL_API_BASE}/target/search").mock(
            return_value=httpx.Response(200, json={"targets": []}),
        )
        assert search_targets("nothing", limit=10) == []

    @respx.mock
    def test_500_raises_dberror(self) -> None:
        respx.get(f"{CHEMBL_API_BASE}/target/search").mock(
            return_value=httpx.Response(500, text="oops"),
        )
        with pytest.raises(DbError) as exc:
            search_targets("x", limit=10)
        assert exc.value.provider == "chembl"
        assert exc.value.status_code == 500


class TestFetchActivities:
    @respx.mock
    def test_returns_filtered_activities(self) -> None:
        body = {
            "activities": [
                {
                    "molecule_chembl_id": "CHEMBL150",
                    "pchembl_value": "8.2",
                    "standard_type": "IC50",
                    "standard_value": "6.3",
                    "standard_units": "nM",
                },
                {
                    "molecule_chembl_id": "CHEMBL151",
                    "pchembl_value": "7.5",
                    "standard_type": "Ki",
                    "standard_value": "32",
                    "standard_units": "nM",
                },
            ],
        }
        respx.get(f"{CHEMBL_API_BASE}/activity").mock(
            return_value=httpx.Response(200, json=body),
        )
        activities = fetch_activities(
            target_chembl_id="CHEMBL2095157",
            pchembl_threshold=6.0,
            limit=50,
        )
        assert len(activities) == 2
        assert activities[0].molecule_chembl_id == "CHEMBL150"
        assert activities[0].pchembl_value == 8.2
        assert activities[0].standard_type == "IC50"

    @respx.mock
    def test_skips_records_with_null_pchembl(self) -> None:
        body = {
            "activities": [
                {
                    "molecule_chembl_id": "CHEMBL_X",
                    "pchembl_value": None,
                    "standard_type": "Inhibition",
                },
                {
                    "molecule_chembl_id": "CHEMBL150",
                    "pchembl_value": "7.0",
                    "standard_type": "IC50",
                    "standard_value": "100",
                    "standard_units": "nM",
                },
            ],
        }
        respx.get(f"{CHEMBL_API_BASE}/activity").mock(
            return_value=httpx.Response(200, json=body),
        )
        activities = fetch_activities("CHEMBL1", pchembl_threshold=6.0, limit=50)
        assert len(activities) == 1
        assert activities[0].molecule_chembl_id == "CHEMBL150"

    @respx.mock
    def test_4xx_raises_dberror(self) -> None:
        respx.get(f"{CHEMBL_API_BASE}/activity").mock(
            return_value=httpx.Response(404, text="not found"),
        )
        with pytest.raises(DbError) as exc:
            fetch_activities("CHEMBL_ZZZ", pchembl_threshold=6.0, limit=50)
        assert exc.value.provider == "chembl"


class TestFetchCompound:
    @respx.mock
    def test_returns_compound(self) -> None:
        body = {
            "molecule_chembl_id": "CHEMBL150",
            "pref_name": "INDINAVIR",
            "molecule_structures": {
                "canonical_smiles": "CC(C)(C)NC(=O)C1CN(Cc2ccccc2)CCN1C[C@H](O)C[C@@H](Cc1ccccc1)C(=O)NC1c2ccccc2CC1O",
            },
            "max_phase": 4,
        }
        respx.get(f"{CHEMBL_API_BASE}/molecule/CHEMBL150").mock(
            return_value=httpx.Response(200, json=body),
        )
        compound = fetch_compound("CHEMBL150")
        assert isinstance(compound, ChemblCompound)
        assert compound.molecule_chembl_id == "CHEMBL150"
        assert compound.pref_name == "INDINAVIR"
        assert "C1CN" in compound.canonical_smiles
        assert compound.max_phase == 4

    @respx.mock
    def test_404_raises_dberror(self) -> None:
        respx.get(f"{CHEMBL_API_BASE}/molecule/CHEMBL_ZZZ").mock(
            return_value=httpx.Response(404, text="not found"),
        )
        with pytest.raises(DbError) as exc:
            fetch_compound("CHEMBL_ZZZ")
        assert exc.value.provider == "chembl"
        assert exc.value.status_code == 404
