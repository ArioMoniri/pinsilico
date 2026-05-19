# Releasing

> Step-by-step for cutting a tagged release. Phase 12 + 14 of [BUILD_PROMPT.md](../BUILD_PROMPT.md).

## 0. One-time setup

### macOS notarization secrets (recommended)

Notarized macOS builds skip the Gatekeeper warning on first launch.
**Skip this section to ship unsigned macOS builds — they still work,
but users will see "macOS cannot verify the developer" on first open.**

Three GitHub Actions secrets are needed.

#### Step 1 — Apple ID app-specific password

1. Go to <https://appleid.apple.com>.
2. Sign in with the Apple ID that owns your Apple Developer Program membership.
3. Under **Sign-In and Security** → **App-Specific Passwords** → **Generate an app-specific password**.
4. Label it `PInSilico notarization` (or anything you'll recognise).
5. Copy the 19-character password (format: `xxxx-xxxx-xxxx-xxxx`).
   You'll never see it again, so don't lose it.

#### Step 2 — Find your Team ID

1. Go to <https://developer.apple.com/account>.
2. Click **Membership Details**.
3. Copy the 10-character **Team ID** (e.g. `AB12CD34EF`).

#### Step 3 — Add the three secrets to GitHub

1. On GitHub, go to your repo: <https://github.com/ArioMoniri/pinsilico>.
2. Click **Settings** (top-right tab).
3. In the left sidebar, click **Secrets and variables** → **Actions**.
4. Click **New repository secret** for each of the three below:

| Secret name | Value |
|---|---|
| `APPLE_ID` | Your Apple ID email (e.g. `moniriario@gmail.com`) |
| `APPLE_PASSWORD` | The 19-char app-specific password from Step 1 |
| `APPLE_TEAM_ID` | The 10-char team ID from Step 2 |

That's it. `release.yml` reads them via `${{ secrets.APPLE_ID }}` etc.
when the tag-triggered build runs the macOS matrix job.

### Windows signing

**Not configured.** Windows builds in `release.yml` are produced
unsigned by design — users will see a Microsoft SmartScreen
"unrecognized app" warning on first launch and need to click
"More info" → "Run anyway". To add Authenticode signing later,
buy a code-signing certificate (Sectigo, DigiCert, etc.) and
extend the `env:` block in `release.yml`. Not in scope for v1.

### Linux signing

Not needed. The `.AppImage` / `.deb` outputs are unsigned by
convention; users trust the SHA256 published in the GitHub
Release notes.

## 1. Populate the bundled-binary checksums

`scripts/binaries.lock.json` ships with `0000…` sentinel hashes. CI's
`release.yml` verify step refuses to proceed against the sentinels.

On a macOS machine, run:

```bash
python scripts/fetch_binaries.py --update
```

This downloads each binary from upstream, computes its SHA256, and
writes it back to the lockfile. **It is fault-tolerant**: any entry
that 404s (e.g. AutoDock Vina v1.2.5 has no native macOS arm64
binary in its GitHub release) is logged with `_pending` and skipped;
every other entry is still updated. Re-run after fixing the URL.

Repeat the command on a Linux box (or a Linux Docker container) and
on a Windows box (or via WSL) to populate the other platform keys.
Each run only touches the entries for its detected OS.

After both runs, review the diff:

```bash
git diff scripts/binaries.lock.json
git commit -am "chore(packaging): populate binary checksums"
git push
```

### When upstream has no binary for your platform

Mark the entry `"_unavailable": true` with a `_reason` explaining
the workaround. The packaging script reads `_unavailable` and skips
the entry without failing the build. Phase 12's `build_app.sh` is
expected to fall back to a source build for these — for now,
document it and ship without that engine on that platform.

Example, already in the lockfile for Vina on macOS arm64:

```json
"macos-arm64": {
  "_unavailable": true,
  "_reason": "AutoDock Vina v1.2.5 has no native macOS arm64 binary. Build from source instead."
}
```

## 2. Bump the version

The version string lives in **six** files. `scripts/release.py`
verifies they all agree before tagging.

| File | What to change |
|---|---|
| `app/src-tauri/Cargo.toml` | `version = "x.y.z"` |
| `app/src-tauri/tauri.conf.json` | `"version": "x.y.z"` |
| `app/package.json` | `"version": "x.y.z"` |
| `sidecar/pyproject.toml` | `version = "x.y.z"` |
| `sidecar/pinsilico/__init__.py` | `__version__: str = "x.y.z"` |
| `app/src/lib/version.ts` | `APP_VERSION = "x.y.z"` |

```bash
# After editing all six:
git add -A
git commit -m "chore: bump version to x.y.z"
```

## 3. Tag and push

```bash
python scripts/release.py vx.y.z
```

This runs the pre-flight checks:

1. Working tree clean
2. Tag doesn't exist locally or on remote
3. All six version files agree on `x.y.z`
4. `make ci` passes (lint + every test suite)

If everything passes, it creates an annotated tag and pushes it.
CI's `release.yml` picks it up immediately and runs the 3-OS matrix.

## 4. Watch the matrix

```bash
gh run watch
```

When all three OSes complete, the `release` job publishes the
GitHub Release with every artefact attached
(`.dmg`, `.AppImage`, `.deb`, `.msi`, `.exe`).

## 5. Smoke-test the installers

Download from the GitHub Release page on a fresh machine and
verify the install + first-launch flow:

- macOS: `.dmg` opens, drag to Applications, launch. If notarization
  succeeded, no Gatekeeper warning.
- Windows: SmartScreen warning is expected for unsigned builds.
  Click "More info" → "Run anyway".
- Linux: `chmod +x *.AppImage && ./*.AppImage`.

## 6. If something breaks

Don't delete the tag. Yank the release (mark it pre-release) and
fix forward with `vx.y.(z+1)`. Tag history is part of the audit
trail.
