import { describe, expect, it } from "vitest";
import { ApiError, PinsilicoClient } from "./api";

const BASE = "http://127.0.0.1:51234";
const TOKEN = "test-token-1234";

function fakeFetch(
  responses: Record<string, { status: number; body: unknown }>,
  capturedRequests: { url: string; init: RequestInit }[] = [],
): typeof fetch {
  return ((url: URL | string | Request, init?: RequestInit) => {
    const u = typeof url === "string" ? url : (url as URL).toString();
    capturedRequests.push({ url: u, init: init ?? {} });
    const match = Object.keys(responses).find((p) => u.endsWith(p));
    if (!match) {
      return Promise.resolve(new Response("not mocked", { status: 599 }));
    }
    const entry = responses[match]!;
    return Promise.resolve(
      new Response(JSON.stringify(entry.body), {
        status: entry.status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }) as unknown as typeof fetch;
}

describe("PinsilicoClient", () => {
  it("sends the auth token on protected routes", async () => {
    const captured: { url: string; init: RequestInit }[] = [];
    const client = new PinsilicoClient({
      apiBase: BASE,
      token: TOKEN,
      fetchImpl: fakeFetch(
        {
          "/version": { status: 200, body: { version: "0.0.1", schema_version: "1" } },
        },
        captured,
      ),
    });
    await client.version();
    expect(captured).toHaveLength(1);
    const headers = captured[0]!.init.headers as Record<string, string>;
    expect(headers["X-Pinsilico-Token"]).toBe(TOKEN);
  });

  it("omits the auth token on /health", async () => {
    const captured: { url: string; init: RequestInit }[] = [];
    const client = new PinsilicoClient({
      apiBase: BASE,
      token: TOKEN,
      fetchImpl: fakeFetch(
        { "/health": { status: 200, body: { status: "ok", version: "0.0.1" } } },
        captured,
      ),
    });
    const r = await client.health();
    expect(r.status).toBe("ok");
    const headers = captured[0]!.init.headers as Record<string, string>;
    expect(headers["X-Pinsilico-Token"]).toBeUndefined();
  });

  it("throws ApiError on non-2xx with the parsed envelope", async () => {
    const client = new PinsilicoClient({
      apiBase: BASE,
      token: TOKEN,
      fetchImpl: fakeFetch({
        "/version": {
          status: 401,
          body: {
            error: {
              code: "INVALID_TOKEN",
              message: "bad token",
              details: { hint: "see stdout" },
            },
          },
        },
      }),
    });
    await expect(client.version()).rejects.toThrowError(ApiError);
    try {
      await client.version();
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      const err = e as ApiError;
      expect(err.status).toBe(401);
      expect(err.code).toBe("INVALID_TOKEN");
      expect(err.details).toEqual({ hint: "see stdout" });
    }
  });

  it("encodes path params safely", async () => {
    const captured: { url: string; init: RequestInit }[] = [];
    const client = new PinsilicoClient({
      apiBase: BASE,
      token: TOKEN,
      fetchImpl: fakeFetch(
        {
          "/db/rcsb/structures/1HSG": {
            status: 200,
            body: {
              identifier: "1HSG",
              title: "",
              organism: null,
              resolution_angstrom: null,
              pdb_text: "HEADER\nEND\n",
            },
          },
        },
        captured,
      ),
    });
    await client.rcsbFetch("1HSG");
    expect(captured[0]!.url).toContain("/db/rcsb/structures/1HSG");
  });

  it("posts pocket/detect with the pdb_text body", async () => {
    const captured: { url: string; init: RequestInit }[] = [];
    const client = new PinsilicoClient({
      apiBase: BASE,
      token: TOKEN,
      fetchImpl: fakeFetch(
        {
          "/pocket/detect": {
            status: 200,
            body: { pockets: [] },
          },
        },
        captured,
      ),
    });
    await client.pocketDetect("HEADER\nEND\n");
    const body = JSON.parse(captured[0]!.init.body as string);
    expect(body.pdb_text).toBe("HEADER\nEND\n");
    expect(body.binary_path).toBe("fpocket");
  });

  it("posts sim/fast_forward and returns parsed counts", async () => {
    const client = new PinsilicoClient({
      apiBase: BASE,
      token: TOKEN,
      fetchImpl: fakeFetch({
        "/sim/fast_forward": {
          status: 200,
          body: { counts: { a: 600, b: 400 }, n_events: 1000 },
        },
      }),
    });
    const out = await client.simFastForward({
      sites: [
        { identifier: "a", centroid_xyz: [0, 0, 0], radius_a: 5, dg_kcal_mol: -8 },
        { identifier: "b", centroid_xyz: [10, 0, 0], radius_a: 5, dg_kcal_mol: -4 },
      ],
      n_events: 1000,
    });
    expect(out.n_events).toBe(1000);
    expect(out.counts).toEqual({ a: 600, b: 400 });
  });
});
