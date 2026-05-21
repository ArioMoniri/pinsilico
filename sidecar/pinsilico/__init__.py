"""PInSilico Python sidecar package.

Houses the FastAPI server, chemistry/docking/pocket/simulation modules, and
the file-IO + session-bundle layers. Imported by the Tauri shell over local
HTTP after PyInstaller bundles this package into a single binary.

Version sync
------------
:data:`__version__` is the single source of truth for the sidecar's version
string. It must equal the ``version`` field in:

* ``sidecar/pyproject.toml`` ``[project].version``
* ``app/package.json``
* ``app/src-tauri/Cargo.toml`` ``[package].version``
* ``app/src-tauri/tauri.conf.json`` ``version``
* ``app/src/lib/version.ts`` ``APP_VERSION``

Phase 12 packaging adds a CI step asserting all six agree.
"""

from __future__ import annotations

__version__: str = "1.7.2"

__all__ = ["__version__"]
