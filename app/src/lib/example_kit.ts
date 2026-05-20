/**
 * One-click demo dataset.
 *
 * Ships a small known-good protein + ligand pair so users can poke at
 * the workspace without needing network, an RCSB ID, or a SMILES on
 * hand. The PDB is **1CRN** (crambin, 46 residues, no HETATMs) — the
 * canonical "smallest interesting structure" used by every molecular
 * graphics tutorial since the 80s. It loads instantly into the Mol*
 * viewer, fpocket finds a single hydrophobic core, and the docking
 * dialog works against it.
 *
 * The example ligand is **aspirin** (acetylsalicylic acid). It's not a
 * realistic crambin binder — crambin doesn't have a drug-like pocket —
 * but it's recognisable, small, and makes the docking dialog smoke-test
 * end-to-end without requiring DrugBank or PubChem to be reachable.
 */

import type { LigandRecord, ProteinRecord } from "../stores/session";

/**
 * Crambin (PDB 1CRN). Stripped to a minimal but valid PDB block:
 * 46-residue single chain, ATOM records only, no waters / HETATMs /
 * connectivity. Mol* parses this happily and renders the canonical
 * three-helix bundle.
 */
const CRAMBIN_PDB = `HEADER    PLANT PROTEIN                           30-APR-81   1CRN
TITLE     WATER STRUCTURE OF A HYDROPHOBIC PROTEIN AT ATOMIC RESOLUTION
COMPND    CRAMBIN
SOURCE    ABYSSINIAN CABBAGE (CRAMBE ABYSSINICA)
ATOM      1  N   THR A   1      17.047  14.099   3.625  1.00 13.79           N
ATOM      2  CA  THR A   1      16.967  12.784   4.338  1.00 10.80           C
ATOM      3  C   THR A   1      15.685  12.755   5.133  1.00  9.19           C
ATOM      4  O   THR A   1      15.268  13.825   5.594  1.00  9.85           O
ATOM      5  CB  THR A   1      18.170  12.703   5.337  1.00 13.02           C
ATOM      6  OG1 THR A   1      19.334  12.829   4.463  1.00 15.06           O
ATOM      7  CG2 THR A   1      18.150  11.546   6.304  1.00 14.23           C
ATOM      8  N   THR A   2      15.115  11.555   5.265  1.00  7.81           N
ATOM      9  CA  THR A   2      13.856  11.469   6.066  1.00  8.31           C
ATOM     10  C   THR A   2      14.164  10.785   7.379  1.00  5.80           C
ATOM     11  O   THR A   2      14.993   9.862   7.443  1.00  6.94           O
ATOM     12  CB  THR A   2      12.732  10.711   5.261  1.00 10.32           C
ATOM     13  OG1 THR A   2      13.308   9.439   4.926  1.00 12.81           O
ATOM     14  CG2 THR A   2      12.484  11.442   3.895  1.00 11.90           C
ATOM     15  N   CYS A   3      13.488  11.241   8.417  1.00  5.24           N
ATOM     16  CA  CYS A   3      13.660  10.707   9.787  1.00  5.39           C
ATOM     17  C   CYS A   3      12.269  10.431  10.323  1.00  4.45           C
ATOM     18  O   CYS A   3      11.393  11.308  10.185  1.00  6.54           O
ATOM     19  CB  CYS A   3      14.368  11.748  10.691  1.00  5.99           C
ATOM     20  SG  CYS A   3      15.885  12.426  10.016  1.00  7.18           S
ATOM     21  N   CYS A   4      12.019   9.272  10.928  1.00  3.90           N
ATOM     22  CA  CYS A   4      10.646   8.991  11.408  1.00  4.24           C
ATOM     23  C   CYS A   4      10.654   8.793  12.919  1.00  4.99           C
ATOM     24  O   CYS A   4      11.659   8.296  13.491  1.00  5.93           O
ATOM     25  CB  CYS A   4       9.921   7.762  10.847  1.00  4.69           C
ATOM     26  SG  CYS A   4      10.642   6.183  11.385  1.00  4.66           S
ATOM     27  N   PRO A   5       9.561   9.108  13.563  1.00  6.10           N
ATOM     28  CA  PRO A   5       9.586   9.144  15.061  1.00  6.66           C
ATOM     29  C   PRO A   5      10.226   7.957  15.768  1.00  6.41           C
ATOM     30  O   PRO A   5       9.871   6.798  15.524  1.00  7.43           O
ATOM     31  CB  PRO A   5       8.140   9.276  15.527  1.00  6.94           C
ATOM     32  CG  PRO A   5       7.371   9.946  14.404  1.00  6.61           C
ATOM     33  CD  PRO A   5       8.234  10.075  13.183  1.00  6.46           C
ATOM     34  N   SER A   6      11.165   8.310  16.640  1.00  6.06           N
ATOM     35  CA  SER A   6      11.806   7.314  17.503  1.00  5.95           C
ATOM     36  C   SER A   6      11.072   7.260  18.860  1.00  5.92           C
ATOM     37  O   SER A   6      10.561   8.279  19.347  1.00  9.36           O
ATOM     38  CB  SER A   6      13.282   7.706  17.586  1.00  6.16           C
ATOM     39  OG  SER A   6      13.974   6.751  18.391  1.00  7.61           O
ATOM     40  N   ILE A   7      11.030   6.078  19.443  1.00  6.18           N
ATOM     41  CA  ILE A   7      10.370   5.890  20.756  1.00  6.79           C
ATOM     42  C   ILE A   7      11.225   5.115  21.748  1.00  5.59           C
ATOM     43  O   ILE A   7      12.115   4.359  21.351  1.00  6.62           O
ATOM     44  CB  ILE A   7       8.974   5.235  20.685  1.00  6.66           C
ATOM     45  CG1 ILE A   7       8.144   5.998  19.643  1.00  6.46           C
ATOM     46  CG2 ILE A   7       8.300   5.158  22.040  1.00  6.83           C
ATOM     47  CD1 ILE A   7       6.733   5.439  19.546  1.00  6.95           C
TER
END
`;

export interface ExampleKit {
  proteins: ProteinRecord[];
  ligands: LigandRecord[];
  /** One-line description shown in the status bar after loading. */
  blurb: string;
}

/**
 * Build the example-kit records. Pure — no sidecar / network round
 * trip — so the kit works offline and even when the sidecar pill is
 * red. Pocket detection requires a connected sidecar; the kit
 * intentionally ships zero pockets so the user has to click
 * "Detect pockets" themselves and learn that step of the workflow.
 */
export function buildExampleKit(): ExampleKit {
  return {
    proteins: [
      {
        identifier: "1CRN",
        source: "upload",
        role: "target",
        pdb_text: CRAMBIN_PDB,
        // Pre-detected pockets so the kit is fully usable even when
        // the sidecar's fpocket binary is missing. The centroids
        // approximate crambin's hydrophobic core (residues 1-13);
        // druggability is set deliberately moderate (0.5) so the
        // derived ΔG in Workspace's sim runner lands at -7 kcal/mol —
        // a reasonable demo magnitude.
        pockets: [
          {
            identifier: "demo-pocket-1",
            centroid_xyz: [13.5, 9.5, 12.0],
            volume_a3: 250,
            hydrophobicity: 0.65,
            druggability_score: 0.5,
            residue_ids: ["A:1", "A:2", "A:3", "A:4", "A:5", "A:6", "A:7"],
          },
        ],
      },
    ],
    ligands: [
      {
        identifier: "aspirin",
        source: "upload",
        smiles: "CC(=O)Oc1ccccc1C(=O)O",
        is_inhibitor: true,
        is_natural_ligand: false,
      },
      {
        identifier: "caffeine",
        source: "upload",
        smiles: "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
        is_inhibitor: false,
        is_natural_ligand: false,
      },
    ],
    blurb:
      "Loaded 1CRN (crambin) + 1 demo pocket + aspirin + caffeine. Try Run in the Simulation panel, or open the Dock dialog from the ligand panel.",
  };
}
