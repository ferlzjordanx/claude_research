import type { Problem, Ticket, TicketStatus } from "./types";

/**
 * In-memory backend that speaks the same HTTP contract as the FastAPI
 * service in Unit 5. It returns real `Response` objects, so the API
 * client cannot tell the difference: swapping it for the real backend
 * is a configuration change, not a code change.
 */
const USERS: Record<string, string> = {
  agent: "agent-password",
  admin: "admin-password",
};

function json(status: number, body: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: {
      "Content-Type":
        status >= 400 ? "application/problem+json" : "application/json",
    },
  });
}

function problem(
  status: number,
  title: string,
  extra: Partial<Problem> = {},
) {
  return json(status, { title, status, ...extra });
}

export function createMockFetch(options: { latencyMs?: number } = {}) {
  const tickets: Ticket[] = [
    {
      id: 1,
      title: "VPN drops every hour",
      description: "Started after the 2.3 client update.",
      priority: "high",
      status: "open",
      created_at: "2026-10-01T09:00:00Z",
    },
    {
      id: 2,
      title: "Request new monitor",
      description: "27-inch for the design team.",
      priority: "low",
      status: "in_progress",
      created_at: "2026-10-02T10:30:00Z",
    },
  ];
  let nextId = 3;
  const latency = options.latencyMs ?? 150;

  return async function mockFetch(
    input: RequestInfo | URL,
    init: RequestInit = {},
  ): Promise<Response> {
    await new Promise((resolve) => setTimeout(resolve, latency));
    if (init.signal?.aborted) {
      throw new DOMException("The operation was aborted.", "AbortError");
    }
    const url = new URL(String(input), "http://mock.local");
    const method = (init.method ?? "GET").toUpperCase();
    const headers = new Headers(init.headers);

    if (url.pathname === "/auth/token" && method === "POST") {
      const form = new URLSearchParams(String(init.body ?? ""));
      const user = form.get("username") ?? "";
      if (USERS[user] && USERS[user] === form.get("password")) {
        return json(200, {
          access_token: `mock-token-${user}`,
          token_type: "bearer",
          expires_in: 1800,
        });
      }
      return problem(401, "Unauthorized", {
        detail: "Incorrect username or password",
      });
    }

    const auth = headers.get("Authorization") ?? "";
    if (!auth.startsWith("Bearer mock-token-")) {
      return problem(401, "Unauthorized", { detail: "Not authenticated" });
    }

    if (url.pathname === "/tickets" && method === "GET") {
      const status = url.searchParams.get("status");
      const items = tickets
        .filter((t) => !status || t.status === status)
        .sort((a, b) => b.id - a.id);
      return json(200, { items, total: items.length });
    }

    if (url.pathname === "/tickets" && method === "POST") {
      const body = JSON.parse(String(init.body ?? "{}"));
      const title = String(body.title ?? "").trim();
      if (title.length < 3 || title.length > 120) {
        return problem(422, "Validation failed", {
          detail: "The request body is invalid.",
          errors: [
            { loc: ["body", "title"], msg: "must be 3-120 characters" },
          ],
        });
      }
      const ticket: Ticket = {
        id: nextId++,
        title,
        description: String(body.description ?? ""),
        priority: body.priority ?? "medium",
        status: "open",
        created_at: new Date().toISOString(),
      };
      tickets.push(ticket);
      return json(201, ticket);
    }

    const match = url.pathname.match(/^\/tickets\/(\d+)$/);
    if (match && method === "PATCH") {
      const ticket = tickets.find((t) => t.id === Number(match[1]));
      if (!ticket) return problem(404, "Not found");
      const body = JSON.parse(String(init.body ?? "{}"));
      ticket.status = body.status as TicketStatus;
      return json(200, ticket);
    }
    return problem(404, "Not found");
  };
}
