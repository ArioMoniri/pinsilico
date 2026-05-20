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

export interface SimRunRequest {
  sites: {
    identifier: string;
    centroid_xyz: [number, number, number];
    radius_a: number;
    dg_kcal_mol: number;
  }[];
  particles?: { position: [number, number, number] }[];
  protein_centers?: [number, number, number][];
  protein_radii?: number[];
  diffusion_coeff_a2_per_frame?: number;
  temperature_k?: number;
  box_size_a?: number;
  use_attraction?: boolean;
  tau0_frames?: number;
  seed?: number;
  n_frames: number;
  mode?: "inhibitor_only" | "ligand_only" | "competition";
}

export interface SimRunResponse {
  final_positions: [number, number, number][];
  bound_site_ids: (string | null)[];
  frames_executed: number;
}

export interface SimStreamFrame {
  frame: number;
  positions: [number, number, number][];
  bound: boolean[];
}

/**
 * Parse one Server-Sent-Events "frame" (the chunk between two `\n\n`
 * separators). Returns `{event, data}` for any frame whose event line
 * matches and whose data line is present; returns null otherwise.
 *
 * The sidecar emits exactly two event types — `frame` (per-step) and
 * `done` (terminator) — so we don't bother with id / retry fields.
 */
function parseSseFrame(raw: string): { event: string; data: string } | null {
  let event: string | null = null;
  let data: string | null = null;
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data = line.slice(5).trim();
  }
  if (event === null || data === null) return null;
  return { event, data };
}

export interface PubChemSdfResponse {
  cid: number;
  sdf_text: string;
}

export interface DrugBankResponse {
  drugbank_id: string;
  name: string;
  smiles: string | null;
}

export interface SessionSavePayloadProtein {
  identifier: string;
  source: string;
  role: string;
  pdb_text: string;
  pockets: {
    identifier: string;
    centroid_xyz: [number, number, number];
    volume_a3?: number;
    hydrophobicity?: number;
    druggability_score?: number;
    residue_ids?: string[];
  }[];
}

export interface SessionSavePayloadLigand {
  identifier: string;
  source: string;
  smiles: string;
  is_inhibitor: boolean;
  is_natural_ligand: boolean;
}

export interface SessionSavePayload {
  seed?: number;
  proteins: SessionSavePayloadProtein[];
  ligands: SessionSavePayloadLigand[];
}

export interface SessionLoadResponse {
  version: string;
  seed: number;
  proteins: SessionSavePayloadProtein[];
  ligands: SessionSavePayloadLigand[];
}

export interface DockingRunRequest {
  engine: "smina" | "vina";
  receptor_pdb: string;
  ligand_smiles: string;
  center_xyz: [number, number, number];
  size_xyz?: [number, number, number];
  exhaustiveness?: number;
  num_modes?: number;
  seed?: number | null;
}

export interface DockingPose {
  rank: number;
  affinity_kcal_mol: number;
  rmsd_lb: number;
  rmsd_ub: number;
}

export interface DockingRunResponse {
  engine: "smina" | "vina";
  poses: DockingPose[];
}

export class PinsilicoClient {
  private readonly config: ClientConfig;
  private readonly fetchFn: typeof fetch;

  constructor(config: ClientConfig) {
    this.config = config;
    // WebKit (Safari / Tauri's WKWebView on macOS) enforces that the
    // global `fetch` is invoked with `this === window`. Holding a bare
    // reference to `fetch` and calling it via a class property strips
    // that binding and throws "Can only call Window.fetch on instances
    // of Window". Bind once in the constructor so every request goes
    // through a properly-bound function.
    this.fetchFn = config.fetchImpl ?? fetch.bind(globalThis);
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

  pubchemSdf(cid: number): Promise<PubChemSdfResponse> {
    return this.request<PubChemSdfResponse>(
      "GET",
      `/db/pubchem/compounds/${encodeURIComponent(String(cid))}/sdf`,
    );
  }

  drugbankFetch(drugbankId: string): Promise<DrugBankResponse> {
    return this.request<DrugBankResponse>(
      "GET",
      `/db/drugbank/drugs/${encodeURIComponent(drugbankId)}`,
    );
  }

  // --------------------------------------------------------------- pocket
  pocketDetect(pdbText: string, binaryPath = "fpocket"): Promise<DetectResponse> {
    return this.request<DetectResponse>("POST", "/pocket/detect", {
      pdb_text: pdbText,
      binary_path: binaryPath,
    });
  }

  // -------------------------------------------------------------- session
  /**
   * POST the workspace state to the sidecar, receive a deterministic
   * `.pinsilico` zip payload. The caller hands the bytes to the
   * browser as a download.
   */
  async sessionSave(payload: SessionSavePayload): Promise<Blob> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Pinsilico-Token": this.config.token,
    };
    const response = await this.fetchFn(`${this.config.apiBase}/session/save`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const envelope = await response.json().catch(() => ({
        error: { code: `HTTP_${response.status}`, message: response.statusText, details: {} },
      }));
      throw new ApiError(response.status, envelope as ErrorEnvelope);
    }
    return await response.blob();
  }

  /**
   * Upload a `.pinsilico` bundle. Returns the parsed contents the
   * workspace folds back into its session store.
   */
  async sessionLoad(file: Blob): Promise<SessionLoadResponse> {
    const headers: Record<string, string> = {
      "X-Pinsilico-Token": this.config.token,
    };
    const body = new FormData();
    body.append("file", file, "session.pinsilico");
    const response = await this.fetchFn(`${this.config.apiBase}/session/load`, {
      method: "POST",
      headers,
      body,
    });
    if (!response.ok) {
      const envelope = await response.json().catch(() => ({
        error: { code: `HTTP_${response.status}`, message: response.statusText, details: {} },
      }));
      throw new ApiError(response.status, envelope as ErrorEnvelope);
    }
    return (await response.json()) as SessionLoadResponse;
  }

  // -------------------------------------------------------------- docking
  dockingRun(req: DockingRunRequest): Promise<DockingRunResponse> {
    return this.request<DockingRunResponse>("POST", "/docking/run", req);
  }

  // ------------------------------------------------------------------ sim
  simRun(req: SimRunRequest): Promise<SimRunResponse> {
    return this.request<SimRunResponse>("POST", "/sim/run", req);
  }

  /**
   * Stream a simulation: each frame the sidecar emits is delivered via
   * `onFrame` as the integration progresses. The native `EventSource`
   * API can't send the per-launch token header, so we hand-roll a
   * minimal SSE parser on top of `fetch` + `ReadableStream`. Resolves
   * to the total frame count once the sidecar emits the `done` event.
   */
  async simStream(
    req: SimRunRequest,
    onFrame: (frame: SimStreamFrame) => void,
    options: { signal?: AbortSignal } = {},
  ): Promise<number> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "X-Pinsilico-Token": this.config.token,
    };
    const init: RequestInit = {
      method: "POST",
      headers,
      body: JSON.stringify(req),
    };
    if (options.signal !== undefined) {
      init.signal = options.signal;
    }
    const response = await this.fetchFn(`${this.config.apiBase}/sim/stream`, init);
    if (!response.ok || response.body === null) {
      const envelope = await response.json().catch(() => ({
        error: { code: `HTTP_${response.status}`, message: response.statusText, details: {} },
      }));
      throw new ApiError(response.status, envelope as ErrorEnvelope);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    let total = 0;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      // SSE frames are separated by a blank line ("\n\n"). Parse off
      // every complete frame in the buffer; leave the partial tail.
      let sep: number;
      while ((sep = buf.indexOf("\n\n")) !== -1) {
        const raw = buf.slice(0, sep);
        buf = buf.slice(sep + 2);
        const parsed = parseSseFrame(raw);
        if (parsed === null) continue;
        if (parsed.event === "frame") {
          const data = JSON.parse(parsed.data) as SimStreamFrame;
          onFrame(data);
        } else if (parsed.event === "done") {
          const done = JSON.parse(parsed.data) as { frames_executed: number };
          total = done.frames_executed;
        }
      }
    }
    return total;
  }

  simFastForward(req: FastForwardRequest): Promise<FastForwardResponse> {
    return this.request<FastForwardResponse>("POST", "/sim/fast_forward", req);
  }

  shutdown(): Promise<{ status: string; message: string }> {
    return this.request<{ status: string; message: string }>("POST", "/shutdown");
  }
}
