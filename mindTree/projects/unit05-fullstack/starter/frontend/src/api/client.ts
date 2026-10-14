import type { Problem } from "./types";

/** Error carrying the HTTP status and the parsed problem body. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly problem: Problem,
    /** Correlates this failure with backend logs (support tickets!). */
    readonly requestId?: string,
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
  newRequestId?: () => string;
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
  const newRequestId =
    opts.newRequestId ?? (() => crypto.randomUUID().replaceAll("-", ""));

  async function request<T>(
    path: string,
    options: RequestOptions = {},
  ): Promise<T> {
    // The same ID appears in the browser console, the response header
    // and every backend log line for this request.
    // TODO(6): send this ID as the X-Request-ID header.
    const requestId = newRequestId();
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

    // Abort when the timeout fires OR when the caller aborts (e.g. a
    // component unmounted).
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    options.signal?.addEventListener("abort", () => controller.abort());

    let response: Response;
    try {
      response = await fetchImpl(`${opts.baseUrl}${path}`, {
        method: options.method ?? "GET",
        headers,
        body,
        signal: controller.signal,
      });
    } catch (err) {
      if (options.signal?.aborted) throw err; // caller cancelled
      throw new ApiError(
        0,
        {
          title: controller.signal.aborted ? "Timeout" : "Network error",
          status: 0,
          detail: controller.signal.aborted
            ? `No response within ${timeoutMs} ms`
            : "Could not reach the server",
        },
        requestId,
      );
    } finally {
      clearTimeout(timer);
    }

    if (response.status === 401) opts.onUnauthorized?.();
    if (!response.ok) {
      let problem: Problem;
      try {
        const data = (await response.json()) as Partial<Problem> & {
          detail?: unknown;
        };
        problem = {
          title: data.title ?? response.statusText ?? "Error",
          status: response.status,
          // FastAPI's default errors put a string in "detail".
          detail: typeof data.detail === "string" ? data.detail : undefined,
          errors: data.errors,
          request_id: data.request_id,
        };
      } catch {
        problem = { title: response.statusText, status: response.status };
      }
      throw new ApiError(
        response.status,
        problem,
        // TODO(7): prefer the server's X-Request-ID response header.
        requestId,
      );
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  return { request };
}
