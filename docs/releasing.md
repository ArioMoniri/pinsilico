# Releasing

> Step-by-step for cutting a tagged release. Phase 12 + 14 of [BUILD_PROMPT.md](../BUILD_PROMPT.md).

## 0. One-time setup

### macOS — pick a path first

Tauri produces a working `.dmg` either way. You have to decide between:

| | **Option A — Signed + Notarized** | **Option B — Unsigned** |
|---|---|---|
| Cost | Apple Developer Program: **$99 / year** | Free |
| Setup time | ~30 min, one-time | None |
| First-launch UX | Clean, no warning | "macOS cannot verify the developer" warning. Right-click → Open → confirm once. After that, normal launch forever. |
| What CI needs | **Three** repo secrets (cert, cert password, app-specific password). Team ID, signing identity, and Apple ID are hardcoded in `release.yml` for this repo. | Nothing |

Both work. Choose A if you're shipping to non-technical users; B if you're shipping to a research lab where everyone can click past a Gatekeeper warning.

> **Important:** Without a signing certificate, the three notarization credentials (Apple ID / password / Team ID) can't sign anything; the `.dmg` ships unsigned. The certificate (`APPLE_CERTIFICATE` + `APPLE_CERTIFICATE_PASSWORD`) is the one piece you can't skip if you want Option A.

> **Baked-in values for this repo's `release.yml`:** the workflow already hardcodes the three public-by-design identifiers so you don't have to add them as secrets:
> - `APPLE_TEAM_ID: FF68N39FU5`
> - `APPLE_SIGNING_IDENTITY: Developer ID Application: Ariorad Moniri (FF68N39FU5)`
> - `APPLE_ID: ariomoniri@icloud.com`
>
> Verify the signing identity matches your actual certificate after import (Step 7 below). If your cert's Common Name is anything else, update `release.yml`'s top-level `env:` block.

### Windows — unsigned by design

`release.yml` does NOT code-sign Windows builds. Users will see a Microsoft SmartScreen "unrecognized app" warning on first launch, click "More info" → "Run anyway", and never see it again. Adding Authenticode requires a $100-400/year cert from Sectigo / DigiCert; out of scope for v1.

### Linux

No signing needed. `.AppImage` / `.deb` are unsigned by convention; users trust the SHA256 published in the GitHub Release notes.

---

## 0a. macOS Option A — Signed + Notarized (3-secret setup with this repo's baked-in defaults)

Skip this entire section if you chose Option B (unsigned).

### Step 1 — Apple Developer Program

1. Enrol at <https://developer.apple.com/programs/enroll>. $99 / year.
2. Wait for the activation email (usually 24-48 hours).

### Step 2 — Generate a Developer ID Application certificate

1. Sign in at <https://developer.apple.com/account>.
2. Click **Certificates, Identifiers & Profiles** → **Certificates** → **+** (create new).
3. Pick **Developer ID Application** (not "Developer ID Installer" — that's for `.pkg` installers).
4. Apple asks for a Certificate Signing Request (CSR).
   - On macOS, open **Keychain Access**.
   - Menu: **Keychain Access** → **Certificate Assistant** → **Request a Certificate From a Certificate Authority…**
   - Email: your Apple ID. Common Name: anything (e.g. "Ario Moniri Developer ID"). Saved to disk. Continue.
   - This produces a `.certSigningRequest` file.
5. Upload the CSR back to Apple. Download the resulting `.cer` file.
6. Double-click the `.cer` — it imports into Keychain Access alongside its private key.

### Step 3 — Export the certificate as `.p12`

1. In Keychain Access, find **"Developer ID Application: Your Name (TEAMID)"** under **My Certificates**.
2. Click the disclosure triangle — it must have a private key under it. If not, the CSR/key pairing didn't import correctly; redo Step 2.4 on the same Mac.
3. Right-click → **Export "Developer ID Application: …"**.
4. Format: **Personal Information Exchange (.p12)**. Save as `developer_id.p12`. Choose a password you'll remember — call it `<P12_PASSWORD>` below.
5. Keychain may ask for your login password to authorise the export.

### Step 4 — Base64-encode the `.p12` for GitHub

```bash
base64 -i developer_id.p12 | pbcopy
```

Now you have the encoded cert on your clipboard, ready to paste into a secret.

### Step 5 — Apple ID app-specific password (for notarization submission)

1. <https://appleid.apple.com> → sign in.
2. **Sign-In and Security** → **App-Specific Passwords** → **Generate**.
3. Label `PInSilico notarization`. Copy the 19-char password (`xxxx-xxxx-xxxx-xxxx`). You won't see it again.

### Step 6 — Find your Team ID

1. <https://developer.apple.com/account> → **Membership Details**.
2. Copy the 10-character **Team ID** (e.g. `AB12CD34EF`).

### Step 7 — Verify your signing identity string

The workflow already has the identity baked in:

```
Developer ID Application: Ariorad Moniri (FF68N39FU5)
```

Verify your imported certificate's Common Name matches **exactly** by running:

```bash
security find-identity -v -p codesigning | grep "Developer ID Application"
```

If the output line differs in any way (different spelling, missing team-ID parens, different case) — copy what the command actually printed and update the `APPLE_SIGNING_IDENTITY:` line in `.github/workflows/release.yml`'s top-level `env:` block.

### Step 8 — Add the THREE secrets to GitHub

The team ID, signing identity, and Apple ID are already baked into `release.yml` for this repo, so you only need three secrets.

1. <https://github.com/ArioMoniri/pinsilico> → **Settings** (top-right) → **Secrets and variables** → **Actions**.
2. Click **New repository secret** three times:

| Name | Value |
|---|---|
| `APPLE_CERTIFICATE` | The base64 string from Step 4 (entire clipboard contents) |
| `APPLE_CERTIFICATE_PASSWORD` | The `<P12_PASSWORD>` from Step 3 |
| `APPLE_PASSWORD` | The 19-char app-specific password from Step 5 |

Done. `release.yml` reads the three secrets on every macOS matrix job and combines them with the baked-in identifiers.

> **If you ever want to rotate the Apple ID, Team ID, or signing identity** — edit the top-level `env:` block in `release.yml` directly (those are not secrets, just defaults).

### How Option A's build actually works (so you can debug failures)

1. Tauri imports `APPLE_CERTIFICATE` (base64) → decodes → installs into a temporary keychain using `APPLE_CERTIFICATE_PASSWORD`.
2. Tauri signs the `.app` bundle with `APPLE_SIGNING_IDENTITY` (must match a cert in the keychain).
3. Tauri builds the `.dmg`.
4. Tauri submits the `.dmg` to Apple's notarization service using `APPLE_ID` + `APPLE_PASSWORD` + `APPLE_TEAM_ID`.
5. Tauri waits for the notarization ticket and staples it to the `.dmg`.
6. Final `.dmg` is uploaded as a release artefact.

If any single secret is missing or wrong, Tauri logs which one and either falls back to an unsigned build (if `APPLE_CERTIFICATE` is missing) or fails the build (if the cert is present but notarization creds are missing).

---

## 0b. macOS Option B — Unsigned (literally zero setup)

Do nothing. Don't add any Apple secrets. `release.yml` detects the missing certificate and runs `pnpm tauri build` without signing. The resulting `.dmg` works fine; users see Gatekeeper on first launch.

Document the bypass in your release notes:

> macOS users: on first launch you'll see "PInSilico cannot be opened because Apple cannot check it for malicious software". Right-click the app → Open → confirm. That's a one-time click; subsequent launches are normal.

---

## 1. Populate the bundled-binary checksums

`scripts/binaries.lock.json` ships with `0000…` sentinel hashes. CI's `release.yml` verify step refuses to proceed against the sentinels.

```bash
python scripts/fetch_binaries.py --update
```

Fault-tolerant: if any URL 404s the script logs `_pending` for that entry and moves on. Re-run after fixing the URL or marking the entry `_unavailable`. Repeat on every supported OS (or a Linux Docker container and a Windows VM).

```bash
git diff scripts/binaries.lock.json
git commit -am "chore(packaging): populate binary checksums"
git push
```

### When upstream has no binary for your platform

Mark the entry `"_unavailable": true` with a `_reason`:

```json
"macos-arm64": {
  "_unavailable": true,
  "_reason": "AutoDock Vina v1.2.5 has no native macOS arm64 binary."
}
```

`fetch_binaries.py` skips it; release notes should document the source-build workaround.

---

## 2. Bump the version (six files, all must agree)

| File | Field |
|---|---|
| `app/src-tauri/Cargo.toml` | `version = "x.y.z"` |
| `app/src-tauri/tauri.conf.json` | `"version": "x.y.z"` |
| `app/package.json` | `"version": "x.y.z"` |
| `sidecar/pyproject.toml` | `version = "x.y.z"` |
| `sidecar/pinsilico/__init__.py` | `__version__: str = "x.y.z"` |
| `app/src/lib/version.ts` | `APP_VERSION = "x.y.z"` |

`scripts/release.py` will refuse to tag if any of the six disagree.

---

## 3. Tag and push

```bash
python scripts/release.py vx.y.z
```

Pre-flight checks: clean tree, unique tag, six-way version sync, `make ci` passes. On success, creates an annotated tag and pushes it — CI's `release.yml` picks it up and runs the 3-OS matrix.

---

## 4. Watch the matrix

```bash
gh run watch
```

When all three OSes complete, the `release` job publishes the GitHub Release with every artefact attached (`.dmg`, `.AppImage`, `.deb`, `.msi`, `.exe`).

---

## 5. Smoke-test the installers

- **macOS Option A:** double-click `.dmg`, drag to Applications, launch. No Gatekeeper warning.
- **macOS Option B:** same, but on first launch right-click → Open → confirm.
- **Windows:** SmartScreen warning. "More info" → "Run anyway".
- **Linux:** `chmod +x *.AppImage && ./*.AppImage`.

---

## 6. If something breaks

Don't delete the tag. Yank the release (mark it pre-release in the GitHub UI) and fix forward with `vx.y.(z+1)`. Tag history is part of the audit trail and rewriting it is worse than shipping a `.1`.
