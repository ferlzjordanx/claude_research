import type { Problem } from "./types";

/** Error carrying the HTTP status and the parsed problem body. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly problem: Problem,
  ) {
    super(problem.detail ?? problem.title);
    this.name = "ApiError";
  }
}

export interface ApiClientOptions {
  baseUrl: string;
  getToken: () => string | null;
  onUnauthorized?: () => void;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: Record<string, string>;
  signal?: AbortSignal;
}

export interface ApiClient {
  request<T>(path: string, options?: RequestOptions): Promise<T>;
}

/**
 * One place for cross-cutting HTTP concerns: base URL, auth header,
 * JSON/form encoding, timeout, error parsing and 401 handling.
 */
export function createApiClient(opts: ApiClientOptions): ApiClient {
  const fetchImpl = opts.fetchImpl ?? globalThis.fetch.bind(globalThis);
  const timeoutMs = opts.timeoutMs ?? 10_000;

  async function request<T>(
    path: string,
    options: RequestOptions = {},
  ): Promise<T> {
    const headers = new Headers({ Accept: "application/json" });
    const token = opts.getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);

    let body: BodyInit | undefined;
    if (options.form) {
      body = new URLSearchParams(options.form);
      headers.set("Content-Type", "application/x-www-form-urlencoded");
    } else if (options.body !== undefined) {
      body = JSON.stringify(options.body);
      headers.set("Content-Type", "application/json");
    }

    // TODO: implement the rest of request():
    // 1. create an AbortController; abort it after `timeoutMs` and when
    //    options.signal aborts
    // 2. call fetchImpl(`${opts.baseUrl}${path}`, {method, headers,
    //    body, signal}); on a thrown error rethrow if the CALLER
    //    aborted, otherwise throw ApiError(0, {title: "Timeout" |
    //    "Network error", ...})
    // 3. on 401 call opts.onUnauthorized?.()
    // 4. on !response.ok parse problem+json (fall back to statusText)
    //    and throw ApiError(response.status, problem)
    // 5. 204 → return undefined; otherwise return response.json()
    void fetchImpl;
    void path;
    void timeoutMs;
    void body;
    throw new Error("TODO: implement request()");
  }

  return { request };
}
