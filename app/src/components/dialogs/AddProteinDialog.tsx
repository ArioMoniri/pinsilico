import { useState, type ChangeEvent, type JSX } from "react";

import { ApiError, type PdbEntryResponse, type PinsilicoClient } from "../../lib/api";
import { proteinFromEntry, useSessionStore } from "../../stores/session";

type Source = "rcsb" | "alphafold" | "upload";

interface AddProteinDialogProps {
  client: PinsilicoClient | null;
  open: boolean;
  onClose: () => void;
  onLoaded?: (protein: PdbEntryResponse, source: Source) => void;
}

/**
 * Modal for loading a protein. Three tabs:
 *
 * * RCSB — 4-char PDB ID (e.g. 1AKE)
 * * AlphaFold — UniProt accession (e.g. P12345)
 * * Upload — paste raw PDB text from a local file
 *
 * Each tab calls the corresponding sidecar route, drops the resulting
 * record into the session store, then closes.
 */
export function AddProteinDialog({
  client,
  open,
  onClose,
  onLoaded,
}: AddProteinDialogProps): JSX.Element | null {
  const [source, setSource] = useState<Source>("rcsb");
  const [pdbId, setPdbId] = useState("");
  const [accession, setAccession] = useState("");
  const [uploadIdentifier, setUploadIdentifier] = useState("");
  const [uploadText, setUploadText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const addProtein = useSessionStore((s) => s.addProtein);

  if (!open) return null;

  const reset = (): void => {
    setPdbId("");
    setAccession("");
    setUploadIdentifier("");
    setUploadText("");
    setError(null);
  };

  const close = (): void => {
    reset();
    onClose();
  };

  const submit = async (): Promise<void> => {
    setError(null);

    if (source === "upload") {
      if (uploadIdentifier.trim() === "" || uploadText.trim() === "") {
        setError("Identifier and PDB text are required for an upload.");
        return;
      }
      const synthetic: PdbEntryResponse = {
        identifier: uploadIdentifier.trim(),
        title: `Uploaded ${uploadIdentifier.trim()}`,
        organism: null,
        resolution_angstrom: null,
        pdb_text: uploadText,
      };
      addProtein(proteinFromEntry(synthetic, "upload"));
      onLoaded?.(synthetic, "upload");
      close();
      return;
    }

    if (client === null) {
      setError("Sidecar is not connected yet — wait for the toolbar pill to turn green.");
      return;
    }

    setLoading(true);
    try {
      const entry =
        source === "rcsb"
          ? await client.rcsbFetch(pdbId.trim())
          : await client.alphafoldFetch(accession.trim());
      addProtein(proteinFromEntry(entry, source));
      onLoaded?.(entry, source);
      close();
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`${e.code}: ${e.message}`);
      } else if (e instanceof Error) {
        setError(e.message);
      } else {
        setError("Unknown error fetching protein.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Add protein"
      style={backdropStyle}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div style={panelStyle}>
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: "1rem" }}>Add protein</h2>
          <button type="button" onClick={close} aria-label="Close" style={iconButtonStyle}>
            ×
          </button>
        </header>

        <nav style={{ display: "flex", gap: "0.25rem", marginTop: "0.75rem" }}>
          {(["rcsb", "alphafold", "upload"] as const).map((s) => (
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
              {s === "rcsb" ? "RCSB" : s === "alphafold" ? "AlphaFold" : "Upload"}
            </button>
          ))}
        </nav>

        <div style={{ marginTop: "0.75rem" }}>
          {source === "rcsb" && (
            <label style={fieldStyle}>
              PDB ID
              <input
                value={pdbId}
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  setPdbId(e.target.value);
                }}
                placeholder="e.g. 1AKE"
                maxLength={8}
                style={inputStyle}
                aria-label="RCSB PDB identifier"
              />
              <small style={hintStyle}>
                4-character identifier from RCSB (case-insensitive). Fetched live from the sidecar.
              </small>
            </label>
          )}

          {source === "alphafold" && (
            <label style={fieldStyle}>
              UniProt accession
              <input
                value={accession}
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  setAccession(e.target.value);
                }}
                placeholder="e.g. P12345"
                maxLength={16}
                style={inputStyle}
                aria-label="UniProt accession for AlphaFold"
              />
              <small style={hintStyle}>
                AlphaFold predicted structures are keyed by UniProt accession.
              </small>
            </label>
          )}

          {source === "upload" && (
            <>
              <div style={fieldStyle}>
                <label htmlFor="upload-file-picker" style={{ marginBottom: "0.25rem" }}>
                  Choose a structure file
                </label>
                <input
                  id="upload-file-picker"
                  type="file"
                  accept=".pdb,.cif,.ent,.pdbqt,text/plain,chemical/x-pdb,chemical/x-cif"
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    const file = e.target.files?.[0];
                    if (file === undefined) return;
                    // Default the identifier to the filename stem so the
                    // user doesn't have to type it manually — they can
                    // still edit the field below.
                    const stem = file.name.replace(/\.[^.]+$/, "");
                    if (uploadIdentifier.trim() === "") {
                      setUploadIdentifier(stem);
                    }
                    const reader = new FileReader();
                    reader.addEventListener("load", () => {
                      const text = reader.result;
                      if (typeof text === "string") {
                        setUploadText(text);
                      }
                    });
                    reader.addEventListener("error", () => {
                      setError(`Could not read file: ${file.name}`);
                    });
                    reader.readAsText(file);
                  }}
                  style={fileInputStyle}
                  aria-label="Upload PDB or mmCIF file"
                />
                <small style={hintStyle}>
                  Supported: <code>.pdb</code>, <code>.cif</code>, <code>.ent</code>,{" "}
                  <code>.pdbqt</code>. The file is read locally — nothing leaves your machine.
                </small>
              </div>
              <label style={fieldStyle}>
                Identifier
                <input
                  value={uploadIdentifier}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    setUploadIdentifier(e.target.value);
                  }}
                  placeholder="A label for this structure"
                  style={inputStyle}
                  aria-label="Upload identifier"
                />
              </label>
              <label style={fieldStyle}>
                PDB text{" "}
                {uploadText.length > 0 && (
                  <small style={hintStyle}>({uploadText.length.toLocaleString()} chars)</small>
                )}
                <textarea
                  value={uploadText}
                  onChange={(e) => {
                    setUploadText(e.target.value);
                  }}
                  placeholder="Pick a file above, or paste the contents of a .pdb file here"
                  rows={6}
                  style={{
                    ...inputStyle,
                    fontFamily: "ui-monospace, monospace",
                    resize: "vertical",
                  }}
                  aria-label="PDB text"
                />
              </label>
            </>
          )}
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

const hintStyle: React.CSSProperties = { color: "#8b9097", fontSize: "0.75rem" };

const fileInputStyle: React.CSSProperties = {
  background: "#0f1115",
  color: "#e6e9ef",
  border: "1px dashed #3a3f48",
  borderRadius: 4,
  padding: "0.6rem",
  fontSize: "0.85rem",
  cursor: "pointer",
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
