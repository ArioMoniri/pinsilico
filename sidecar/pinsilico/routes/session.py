"""HTTP routes for `.pinsilico` session bundles.

Wraps :mod:`pinsilico.session.bundle` (the deterministic zip-based
serialisation that already shipped in Phase 10) so the frontend can
save/load a workspace from the toolbar without going through Tauri's
file plugin. The webview hits these routes with the per-launch token
like any other API call.

Two routes:

* `POST /session/save` — accepts a JSON `SessionBundle` payload, returns
  the deterministic zip bytes (`application/zip`) the frontend
  downloads as `<name>.pinsilico`.
* `POST /session/load` — accepts a `multipart/form-data` upload of a
  `.pinsilico` file, parses it, and returns the JSON `SessionBundle`
  the workspace can fold back into its session store.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from pinsilico import __version__
from pinsilico.session.bundle import (
    SessionBundle,
    SessionLigand,
    SessionPocket,
    SessionProtein,
    load_bundle,
    save_bundle,
)

router = APIRouter(prefix="/session", tags=["session"])


class SessionPocketPayload(BaseModel):
    identifier: str
    centroid_xyz: tuple[float, float, float]
    volume_a3: float = 0.0
    hydrophobicity: float = 0.0
    druggability_score: float = 0.0
    residue_ids: list[str] = Field(default_factory=list)


class SessionProteinPayload(BaseModel):
    identifier: str
    source: str
    role: str
    pdb_text: str
    pockets: list[SessionPocketPayload] = Field(default_factory=list)


class SessionLigandPayload(BaseModel):
    identifier: str
    source: str
    smiles: str
    is_inhibitor: bool = False
    is_natural_ligand: bool = False


class SaveSessionRequest(BaseModel):
    seed: int = 0
    proteins: list[SessionProteinPayload] = Field(default_factory=list)
    ligands: list[SessionLigandPayload] = Field(default_factory=list)


class LoadSessionResponse(BaseModel):
    """JSON-shaped echo of a SessionBundle for the frontend store."""

    version: str
    seed: int
    proteins: list[SessionProteinPayload]
    ligands: list[SessionLigandPayload]


def _to_bundle(req: SaveSessionRequest) -> SessionBundle:
    """Frontend payload → dataclass tree the bundle module expects."""
    return SessionBundle(
        version=__version__,
        seed=req.seed,
        proteins=[
            SessionProtein(
                identifier=p.identifier,
                source=p.source,
                role=p.role,
                pdb_text=p.pdb_text,
                pockets=[
                    SessionPocket(
                        identifier=pk.identifier,
                        centroid_xyz=pk.centroid_xyz,
                        volume_a3=pk.volume_a3,
                        hydrophobicity=pk.hydrophobicity,
                        druggability_score=pk.druggability_score,
                        residue_ids=tuple(pk.residue_ids),
                    )
                    for pk in p.pockets
                ],
            )
            for p in req.proteins
        ],
        ligands=[
            SessionLigand(
                identifier=lig.identifier,
                source=lig.source,
                smiles=lig.smiles,
                is_inhibitor=lig.is_inhibitor,
                is_natural_ligand=lig.is_natural_ligand,
            )
            for lig in req.ligands
        ],
    )


@router.post(
    "/save",
    summary="Serialise the workspace to a deterministic .pinsilico bundle",
    response_class=Response,
)
def save_session(req: Annotated[SaveSessionRequest, Body()]) -> Response:
    bundle = _to_bundle(req)
    with tempfile.NamedTemporaryFile(suffix=".pinsilico", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        save_bundle(bundle, tmp_path)
        payload = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
    filename = f"session-{__version__}.pinsilico"
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/load",
    response_model=LoadSessionResponse,
    summary="Parse a .pinsilico bundle and return its contents as JSON",
)
async def load_session(
    file: Annotated[UploadFile, File(description="A .pinsilico bundle")],
) -> LoadSessionResponse:
    payload = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pinsilico", delete=False) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    try:
        try:
            bundle = load_bundle(tmp_path)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not parse bundle: {exc}",
            ) from exc
    finally:
        # ASYNC240 — Path.unlink is fine here because cleanup is best-effort
        # and the temp file is local; switching to anyio just to satisfy the
        # lint would add a dep for no real-world benefit.
        tmp_path.unlink(missing_ok=True)  # noqa: ASYNC240

    return LoadSessionResponse(
        version=bundle.version,
        seed=bundle.seed,
        proteins=[
            SessionProteinPayload(
                identifier=p.identifier,
                source=p.source,
                role=p.role,
                pdb_text=p.pdb_text,
                pockets=[
                    SessionPocketPayload(
                        identifier=pk.identifier,
                        centroid_xyz=pk.centroid_xyz,
                        volume_a3=pk.volume_a3,
                        hydrophobicity=pk.hydrophobicity,
                        druggability_score=pk.druggability_score,
                        residue_ids=list(pk.residue_ids),
                    )
                    for pk in p.pockets
                ],
            )
            for p in bundle.proteins
        ],
        ligands=[
            SessionLigandPayload(
                identifier=lig.identifier,
                source=lig.source,
                smiles=lig.smiles,
                is_inhibitor=lig.is_inhibitor,
                is_natural_ligand=lig.is_natural_ligand,
            )
            for lig in bundle.ligands
        ],
    )


__all__: list[str] = ["router"]
