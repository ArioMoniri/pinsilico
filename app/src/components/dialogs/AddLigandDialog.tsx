import { useState, type ChangeEvent, type JSX } from "react";

import { ApiError, type PinsilicoClient } from "../../lib/api";
import type { LigandRecord } from "../../stores/session";
import { useSessionStore } from "../../stores/session";

type Source = "smiles" | "chembl" | "pubchem" | "drugbank" | "upload";

interface AddLigandDialogProps {
  client: PinsilicoClient | null;
  open: boolean;
  onClose: () => void;
  onLoaded?: (ligand: LigandRecord) => void;
}

/**
 * Modal for adding a ligand. Five tabs:
 *
 * * SMILES — paste a SMILES string directly (no sidecar round-trip).
 * * ChEMBL — look up by molecule_chembl_id, sidecar returns canonical SMILES.
 * * PubChem — look up SMILES by compound CID via the PubChem proxy.
 * * DrugBank — look up by DrugBank identifier (DBxxxxx).
 * * Upload — read an SDF file locally.
 *
 * The SMILES path stays purely client-side; the others hit the
 * corresponding `/db/*` sidecar routes already shipped in Phase 2.
 */
export function AddLigandDialog({
  client,
  open,
  onClose,
  onLoaded,
}: AddLigandDialogProps): JSX.Element | null {
  const [source, setSource] = useState<Source>("smiles");
  const [smilesInput, setSmilesInput] = useState("");
  const [smilesIdentifier, setSmilesIdentifier] = useState("");
  const [chemblId, setChemblId] = useState("");
  const [pubchemCid, setPubchemCid] = useState("");
  const [drugbankId, setDrugbankId] = useState("");
  const [uploadIdentifier, setUploadIdentifier] = useState("");
  const [uploadSmiles, setUploadSmiles] = useState("");
  const [isInhibitor, setIsInhibitor] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const addLigand = useSessionStore((s) => s.addLigand);

  if (!open) return null;

  const reset = (): void => {
    setSmilesInput("");
    setSmilesIdentifier("");
    setChemblId("");
    setPubchemCid("");
    setDrugbankId("");
    setUploadIdentifier("");
    setUploadSmiles("");
    setIsInhibitor(true);
    setError(null);
  };

  const close = (): void => {
    reset();
    onClose();
  };

  const finishWithRecord = (record: LigandRecord): void => {
    addLigand(record);
    onLoaded?.(record);
    close();
  };

  const submit = async (): Promise<void> => {
    setError(null);

    if (source === "smiles") {
      if (smilesInput.trim() === "" || smilesIdentifier.trim() === "") {
        setError("Both an identifier and a SMILES string are required.");
        return;
      }
      finishWithRecord({
        identifier: smilesIdentifier.trim(),
        source: "upload",
        smiles: smilesInput.trim(),
        is_inhibitor: isInhibitor,
        is_natural_ligand: false,
      });
      return;
    }

    if (source === "upload") {
      if (uploadIdentifier.trim() === "" || uploadSmiles.trim() === "") {
        setError("Pick a file containing a SMILES line, or paste one below.");
        return;
      }
      finishWithRecord({
        identifier: uploadIdentifier.trim(),
        source: "upload",
        smiles: uploadSmiles.trim(),
        is_inhibitor: isInhibitor,
        is_natural_ligand: false,
      });
      return;
    }

    if (client === null) {
      setError("Sidecar is not connected yet — wait for the toolbar pill to turn green.");
      return;
    }

    setLoading(true);
    try {
      if (source === "chembl") {
        const compound = await client.chemblCompound(chemblId.trim());
        if (compound.canonical_smiles === null) {
          throw new Error(`ChEMBL has no canonical SMILES for ${compound.molecule_chembl_id}.`);
        }
        finishWithRecord({
          identifier: compound.molecule_chembl_id,
          source: "chembl",
          smiles: compound.canonical_smiles,
          is_inhibitor: isInhibitor,
          is_natural_ligand: false,
        });
      } else if (source === "pubchem") {
        const cid = Number.parseInt(pubchemCid.trim(), 10);
        if (Number.isNaN(cid)) {
          throw new Error("PubChem CID must be a number.");
        }
        const sdf = await client.pubchemSdf(cid);
        // PubChem SDFs put the SMILES in the > <CANONICAL_SMILES> block.
        // For v1.1.0 we extract it with a best-effort regex; failed
        // extraction surfaces a user-readable error.
        const match = sdf.sdf_text.match(/>\s*<.*SMILES.*>\s*\n([^\n]+)/i);
        const smiles = match?.[1]?.trim();
        if (smiles === undefined || smiles === "") {
          throw new Error(
            `PubChem SDF for CID ${cid} has no SMILES tag — try the ChEMBL or SMILES paths instead.`,
          );
        }
        finishWithRecord({
          identifier: `CID${cid}`,
          source: "pubchem",
          smiles,
          is_inhibitor: isInhibitor,
          is_natural_ligand: false,
        });
      } else if (source === "drugbank") {
        const drug = await client.drugbankFetch(drugbankId.trim());
        if (drug.smiles === null) {
          throw new Error(`DrugBank entry ${drug.drugbank_id} has no SMILES.`);
        }
        finishWithRecord({
          identifier: drug.drugbank_id,
          source: "drugbank",
          smiles: drug.smiles,
          is_inhibitor: isInhibitor,
          is_natural_ligand: false,
        });
      }
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`${e.code}: ${e.message}`);
      } else if (e instanceof Error) {
        setError(e.message);
      } else {
        setError("Unknown error fetching ligand.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Add ligand"
      style={backdropStyle}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div style={panelStyle}>
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: "1rem" }}>Add ligand</h2>
          <button type="button" onClick={close} aria-label="Close" style={iconButtonStyle}>
            ×
          </button>
        </header>

        <nav style={{ display: "flex", gap: "0.25rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
          {(["smiles", "chembl", "pubchem", "drugbank", "upload"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setSource(s);
                setError(null);
              }}
              aria-pressed={source === s}
              style={source === s ? tabActiveStyle : tabStyle}
            >
              {s === "smiles"
                ? "SMILES"
                : s === "chembl"
                  ? "ChEMBL"
                  : s === "pubchem"
                    ? "PubChem"
                    : s === "drugbank"
                      ? "DrugBank"
                      : "Upload SDF"}
            </button>
          ))}
        </nav>

        <div style={{ marginTop: "0.75rem" }}>
          {source === "smiles" && (
            <>
              <label style={fieldStyle}>
                Identifier
                <input
                  value={smilesIdentifier}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    setSmilesIdentifier(e.target.value);
                  }}
                  placeholder="A label for this ligand"
                  style={inputStyle}
                  aria-label="SMILES identifier"
                />
              </label>
              <label style={fieldStyle}>
                SMILES
                <input
                  value={smilesInput}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    setSmilesInput(e.target.value);
                  }}
                  placeholder="CC(=O)Oc1ccccc1C(=O)O"
                  style={{ ...inputStyle, fontFamily: "ui-monospace, monospace" }}
                  aria-label="SMILES string"
                />
                <small style={hintStyle}>
                  Pure client-side path — no sidecar call, no network.
                </small>
              </label>
            </>
          )}

          {source === "chembl" && (
            <label style={fieldStyle}>
              ChEMBL ID
              <input
                value={chemblId}
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  setChemblId(e.target.value);
                }}
                placeholder="e.g. CHEMBL25"
                style={inputStyle}
                aria-label="ChEMBL molecule identifier"
              />
              <small style={hintStyle}>Sidecar fetches the canonical SMILES from ChEMBL.</small>
            </label>
          )}

          {source === "pubchem" && (
            <label style={fieldStyle}>
              PubChem CID
              <input
                value={pubchemCid}
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  setPubchemCid(e.target.value);
                }}
                placeholder="e.g. 2244 (aspirin)"
                style={inputStyle}
                aria-label="PubChem compound CID"
              />
              <small style={hintStyle}>SMILES extracted from the SDF the sidecar returns.</small>
            </label>
          )}

          {source === "drugbank" && (
            <label style={fieldStyle}>
              DrugBank ID
              <input
                value={drugbankId}
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  setDrugbankId(e.target.value);
                }}
                placeholder="e.g. DB00945"
                style={inputStyle}
                aria-label="DrugBank identifier"
              />
              <small style={hintStyle}>
                Requires the bundled DrugBank CSV — see <code>sidecar/resources/</code>.
              </small>
            </label>
          )}

          {source === "upload" && (
            <>
              <div style={fieldStyle}>
                <label htmlFor="ligand-file-picker" style={{ marginBottom: "0.25rem" }}>
                  Choose an SDF / MOL file
                </label>
                <input
                  id="ligand-file-picker"
                  type="file"
                  accept=".sdf,.mol,.mol2,.smi,text/plain,chemical/x-mdl-sdfile"
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    const file = e.target.files?.[0];
                    if (file === undefined) return;
                    const stem = file.name.replace(/\.[^.]+$/, "");
                    if (uploadIdentifier.trim() === "") {
                      setUploadIdentifier(stem);
                    }
                    const reader = new FileReader();
                    reader.addEventListener("load", () => {
                      const text = reader.result;
                      if (typeof text !== "string") return;
                      // Quick best-effort SMILES extraction:
                      //   - .smi: first whitespace-separated token on line 1
                      //   - .sdf/.mol with <SMILES> tag: the line below it
                      const smiTag = /^>\s*<.*SMILES.*>\s*\n([^\n]+)/im.exec(text);
                      if (smiTag !== null) {
                        setUploadSmiles(smiTag[1]?.trim() ?? "");
                        return;
                      }
                      const firstLine = text.trim().split(/\s+/)[0] ?? "";
                      if (
                        /^[A-Za-z0-9@+\-=#$()/[\]%.\\]+$/.test(firstLine) &&
                        firstLine.length > 1
                      ) {
                        setUploadSmiles(firstLine);
                      }
                    });
                    reader.addEventListener("error", () => {
                      setError(`Could not read file: ${file.name}`);
                    });
                    reader.readAsText(file);
                  }}
                  style={fileInputStyle}
                  aria-label="Upload SDF or MOL file"
                />
                <small style={hintStyle}>
                  We try to extract the SMILES from the file. If extraction fails, paste it below.
                </small>
              </div>
              <label style={fieldStyle}>
                Identifier
                <input
                  value={uploadIdentifier}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    setUploadIdentifier(e.target.value);
                  }}
                  placeholder="A label for this ligand"
                  style={inputStyle}
                  aria-label="Upload identifier"
                />
              </label>
              <label style={fieldStyle}>
                SMILES
                <input
                  value={uploadSmiles}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    setUploadSmiles(e.target.value);
                  }}
                  placeholder="Auto-extracted, or paste manually"
                  style={{ ...inputStyle, fontFamily: "ui-monospace, monospace" }}
                  aria-label="SMILES string"
                />
              </label>
            </>
          )}

          <label style={inhibitorRowStyle}>
            <input
              type="checkbox"
              checked={isInhibitor}
              onChange={(e) => {
                setIsInhibitor(e.target.checked);
              }}
            />
            <span>Treat as inhibitor candidate (competes with the natural ligand)</span>
          </label>
        </div>

        {error !== null && (
          <p role="alert" style={errorStyle}>
            {error}
          </p>
        )}

        <footer
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "0.5rem",
            marginTop: "0.75rem",
          }}
        >
          <button type="button" onClick={close} style={secondaryButtonStyle}>
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              void submit();
            }}
            disabled={loading}
            style={primaryButtonStyle}
          >
            {loading ? "Loading…" : "Add"}
          </button>
        </footer>
      </div>
    </div>
  );
}

const backdropStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(8, 10, 14, 0.65)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 100,
};

const panelStyle: React.CSSProperties = {
  background: "#13161c",
  color: "#e6e9ef",
  border: "1px solid #20242b",
  borderRadius: 8,
  padding: "1rem",
  width: "min(560px, calc(100vw - 4rem))",
  boxShadow: "0 8px 24px rgba(0, 0, 0, 0.6)",
};

const tabStyle: React.CSSProperties = {
  background: "transparent",
  color: "#b6bcc6",
  border: "1px solid #2a2f38",
  padding: "0.3rem 0.75rem",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: "0.85rem",
};

const tabActiveStyle: React.CSSProperties = {
  ...tabStyle,
  background: "#1d2129",
  color: "#e6e9ef",
  borderColor: "#3d6eb8",
};

const fieldStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.25rem",
  marginBottom: "0.6rem",
};

const inputStyle: React.CSSProperties = {
  background: "#0f1115",
  color: "#e6e9ef",
  border: "1px solid #2a2f38",
  borderRadius: 4,
  padding: "0.4rem 0.5rem",
  fontSize: "0.9rem",
};

const fileInputStyle: React.CSSProperties = {
  background: "#0f1115",
  color: "#e6e9ef",
  border: "1px dashed #3a3f48",
  borderRadius: 4,
  padding: "0.6rem",
  fontSize: "0.85rem",
  cursor: "pointer",
};

const hintStyle: React.CSSProperties = { color: "#8b9097", fontSize: "0.75rem" };

const inhibitorRowStyle: React.CSSProperties = {
  display: "flex",
  gap: "0.4rem",
  alignItems: "center",
  marginTop: "0.5rem",
  fontSize: "0.78rem",
  color: "#b6bcc6",
};

const primaryButtonStyle: React.CSSProperties = {
  background: "#3d6eb8",
  color: "#fff",
  border: "1px solid #5483c9",
  padding: "0.4rem 1rem",
  borderRadius: 4,
  cursor: "pointer",
  fontWeight: 600,
};

const secondaryButtonStyle: React.CSSProperties = {
  background: "transparent",
  color: "#b6bcc6",
  border: "1px solid #2a2f38",
  padding: "0.4rem 1rem",
  borderRadius: 4,
  cursor: "pointer",
};

const iconButtonStyle: React.CSSProperties = {
  background: "transparent",
  color: "#b6bcc6",
  border: "none",
  fontSize: "1.4rem",
  cursor: "pointer",
  lineHeight: 1,
};

const errorStyle: React.CSSProperties = {
  background: "#3b1c1c",
  color: "#f0a0a0",
  border: "1px solid #7a3535",
  padding: "0.4rem 0.6rem",
  borderRadius: 4,
  marginTop: "0.5rem",
  fontSize: "0.85rem",
};
