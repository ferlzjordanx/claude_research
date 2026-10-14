import { describe, expect, it, vi } from "vitest";
import { ApiError, createApiClient } from "./client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("createApiClient", () => {
  it("sends the bearer token and JSON body", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(201, { id: 1 }));
    const client = createApiClient({
      baseUrl: "/api",
      getToken: () => "abc",
      fetchImpl,
    });
    await client.request("/tickets", { method: "POST", body: { a: 1 } });

    const [url, init] = fetchImpl.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    const headers = new Headers(init.headers);
    expect(url).toBe("/api/tickets");
    expect(headers.get("Authorization")).toBe("Bearer abc");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init.body).toBe('{"a":1}');
  });

  it("form-encodes login bodies", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, {}));
    const client = createApiClient({
      baseUrl: "",
      getToken: () => null,
      fetchImpl,
    });
    await client.request("/auth/token", {
      method: "POST",
      form: { username: "a" },
    });
    const init = (
      fetchImpl.mock.calls[0] as unknown as [string, RequestInit]
    )[1];
    expect(String(init.body)).toBe("username=a");
  });

  it("turns problem+json into ApiError", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(409, {
        title: "Conflict",
        status: 409,
        detail: "Duplicate",
      }),
    );
    const client = createApiClient({
      baseUrl: "",
      getToken: () => null,
      fetchImpl,
    });
    const error = await client.request("/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).message).toBe("Duplicate");
  });

  it("calls onUnauthorized on 401", async () => {
    const onUnauthorized = vi.fn();
    const fetchImpl = vi.fn(async () =>
      jsonResponse(401, { detail: "Invalid or expired token" }),
    );
    const client = createApiClient({
      baseUrl: "",
      getToken: () => "old",
      fetchImpl,
      onUnauthorized,
    });
    await expect(client.request("/x")).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("times out slow requests", async () => {
    const fetchImpl = vi.fn(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
        }),
    );
    const client = createApiClient({
      baseUrl: "",
      getToken: () => null,
      fetchImpl,
      timeoutMs: 20,
    });
    const error = (await client
      .request("/slow")
      .catch((e: unknown) => e)) as ApiError;
    expect(error.status).toBe(0);
    expect(error.problem.title).toBe("Timeout");
  });

  it("returns undefined for 204", async () => {
    const fetchImpl = vi.fn(
      async () => new Response(null, { status: 204 }),
    );
    const client = createApiClient({
      baseUrl: "",
      getToken: () => null,
      fetchImpl,
    });
    await expect(
      client.request("/x", { method: "DELETE" }),
    ).resolves.toBeUndefined();
  });

  it("sends X-Request-ID and attaches it to errors", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(
          JSON.stringify({ title: "Boom", status: 500, request_id: "r1" }),
          { status: 500, headers: { "X-Request-ID": "r1" } },
        ),
    );
    const client = createApiClient({
      baseUrl: "",
      getToken: () => null,
      fetchImpl,
      newRequestId: () => "r1",
    });
    const error = (await client
      .request("/x")
      .catch((e: unknown) => e)) as ApiError;
    const init = (
      fetchImpl.mock.calls[0] as unknown as [string, RequestInit]
    )[1];
    expect(new Headers(init.headers).get("X-Request-ID")).toBe("r1");
    expect(error.requestId).toBe("r1");
    expect(error.problem.request_id).toBe("r1");
  });
});
