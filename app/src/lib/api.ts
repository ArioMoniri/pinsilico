/**
 * Typed client for the PInSilico sidecar HTTP API.
 *
 * Phase 7 ships a hand-written client matching every Phase 5 route.
 * Phase 12 packaging adds an `openapi-typescript` generator step that
 * regenerates this file from the live OpenAPI 3.1 schema — until then
 * the types here are the source of truth and `make ci` includes a
 * contract test that pings each route to confirm the shapes still match.
 *
 * Auth: every call (except `/health`) sends the per-launch token in the
 * `X-Pinsilico-Token` header. The token + API base are read from Tauri
 * IPC commands (`get_api_base()`, `get_token()`) that the Rust shell
 * exposes once the sidecar's stdout banner has been parsed.
 */

export interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, envelope: ErrorEnvelope) {
    super(envelope.error.message);
    this.status = status;
    this.code = envelope.error.code;
    this.details = envelope.error.details;
    this.name = "ApiError";
  }
}

export interface ClientConfig {
  apiBase: string;
  token: string;
  /** Override for tests; defaults to global `fetch`. */
  fetchImpl?: typeof fetch;
}

/** Health probe response (the only unauthenticated route). */
export interface HealthResponse {
  status: "ok";
  version: string;
}

/** /version response. */
export interface VersionResponse {
  version: string;
  schema_version: string;
}

export interface PdbEntryResponse {
  identifier: string;
  title: string;
  organism: string | null;
  resolution_angstrom: number | null;
  pdb_text: string;
}

export interface IdentifierList {
  identifiers: string[];
}

export interface UniProtResponse {
  accession: string;
  description: string;
  sequence: string;
}

export interface ChemblTargetResponse {
  target_chembl_id: string;
  pref_name: string;
  organism: string | null;
}

export interface ChemblCompoundResponse {
  molecule_chembl_id: string;
  pref_name: string | null;
  canonical_smiles: string;
  max_phase: number | null;
}

export interface PubChemSmilesResponse {
  smiles: string;
  cid: number;
}

export interface PocketResponse {
  identifier: string;
  centroid_xyz: [number, number, number];
  volume_a3: number;
  hydrophobicity: number;
  druggability_score: number;
  residue_ids: string[];
}

export interface DetectResponse {
  pockets: PocketResponse[];
}

export interface FastForwardRequest {
  sites: {
    identifier: string;
    centroid_xyz: [number, number, number];
    radius_a: number;
    dg_kcal_mol: number;
  }[];
  temperature_k?: number;
  seed?: number;
  n_events: number;
}

export interface FastForwardResponse {
  counts: Record<string, number>;
  n_events: number;
}

export class PinsilicoClient {
  private readonly config: ClientConfig;

  constructor(config: ClientConfig) {
    this.config = config;
  }

  private get fetchFn(): typeof fetch {
    return this.config.fetchImpl ?? fetch;
  }

  private async request<T>(
    method: "GET" | "POST",
    path: string,
    body?: unknown,
    requiresAuth = true,
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (requiresAuth) {
      headers["X-Pinsilico-Token"] = this.config.token;
    }
    const init: RequestInit = { method, headers };
    if (body !== undefined) {
      init.body = JSON.stringify(body);
    }
    const response = await this.fetchFn(`${this.config.apiBase}${path}`, init);
    if (!response.ok) {
      let envelope: ErrorEnvelope;
      try {
        envelope = (await response.json()) as ErrorEnvelope;
      } catch {
        envelope = {
          error: {
            code: `HTTP_${response.status}`,
            message: response.statusText || "Unknown error",
            details: {},
          },
        };
      }
      throw new ApiError(response.status, envelope);
    }
    return (await response.json()) as T;
  }

  // ---------------------------------------------------------------- unauth
  health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("GET", "/health", undefined, false);
  }

  version(): Promise<VersionResponse> {
    return this.request<VersionResponse>("GET", "/version");
  }

  // -------------------------------------------------------------------- db
  rcsbFetch(pdbId: string): Promise<PdbEntryResponse> {
    return this.request<PdbEntryResponse>(
      "GET",
      `/db/rcsb/structures/${encodeURIComponent(pdbId)}`,
    );
  }

  rcsbSearch(q: string, limit = 25): Promise<IdentifierList> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return this.request<IdentifierList>("GET", `/db/rcsb/search?${params.toString()}`);
  }

  uniprotFetch(accession: string): Promise<UniProtResponse> {
    return this.request<UniProtResponse>(
      "GET",
      `/db/uniprot/proteins/${encodeURIComponent(accession)}`,
    );
  }

  alphafoldFetch(accession: string): Promise<PdbEntryResponse> {
    return this.request<PdbEntryResponse>(
      "GET",
      `/db/alphafold/structures/${encodeURIComponent(accession)}`,
    );
  }

  chemblTargets(q: string, limit = 25): Promise<ChemblTargetResponse[]> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return this.request<ChemblTargetResponse[]>("GET", `/db/chembl/targets?${params.toString()}`);
  }

  chemblCompound(moleculeId: string): Promise<ChemblCompoundResponse> {
    return this.request<ChemblCompoundResponse>(
      "GET",
      `/db/chembl/compounds/${encodeURIComponent(moleculeId)}`,
    );
  }

  pubchemBySmiles(smiles: string): Promise<PubChemSmilesResponse> {
    const params = new URLSearchParams({ smiles });
    return this.request<PubChemSmilesResponse>("GET", `/db/pubchem/by_smiles?${params.toString()}`);
  }

  // --------------------------------------------------------------- pocket
  pocketDetect(pdbText: string, binaryPath = "fpocket"): Promise<DetectResponse> {
    return this.request<DetectResponse>("POST", "/pocket/detect", {
      pdb_text: pdbText,
      binary_path: binaryPath,
    });
  }

  // ------------------------------------------------------------------ sim
  simFastForward(req: FastForwardRequest): Promise<FastForwardResponse> {
    return this.request<FastForwardResponse>("POST", "/sim/fast_forward", req);
  }

  shutdown(): Promise<{ status: string; message: string }> {
    return this.request<{ status: string; message: string }>("POST", "/shutdown");
  }
}
