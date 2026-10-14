import type {
  AiTriage,
  Problem,
  Reply,
  Role,
  Ticket,
  TicketStatus,
} from "./types";

/**
 * In-memory backend that speaks the same HTTP contract as the FastAPI
 * service in Unit 5. It returns real `Response` objects, so the API
 * client cannot tell the difference: swapping it for the real backend
 * is a configuration change, not a code change.
 */
const USERS: Record<string, { password: string; role: Role }> = {
  agent: { password: "agent-password", role: "agent" },
  alice: { password: "alice-password", role: "requester" },
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

function triage(
  category: AiTriage["category"],
  priority: AiTriage["priority"],
): AiTriage {
  return {
    status: "done",
    category,
    priority,
    summary: "Customer needs help.",
    confidence: 0.9,
    needs_human: false,
  };
}

export function createMockFetch(options: { latencyMs?: number } = {}) {
  const tickets: Ticket[] = [
    {
      id: 1,
      title: "Express parcel late",
      description: "Order ORD-1003 was due yesterday.",
      priority: "high",
      status: "open",
      owner: "alice",
      created_at: "2026-10-01T09:00:00Z",
      ai: triage("delivery", "high"),
    },
    {
      id: 2,
      title: "Invoice shows wrong amount",
      description: "Charged twice for one order.",
      priority: "low",
      status: "in_progress",
      owner: "bob",
      created_at: "2026-10-02T10:30:00Z",
      ai: triage("billing", "medium"),
    },
  ];
  const replies: Reply[] = [];
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
      if (USERS[user] && USERS[user].password === form.get("password")) {
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
    const username = auth.replace("Bearer mock-token-", "");
    const me = USERS[username];
    if (!auth.startsWith("Bearer mock-token-") || !me) {
      return problem(401, "Unauthorized", { detail: "Not authenticated" });
    }
    // Same rule as the backend: requesters only see their own tickets.
    const visible = (t: Ticket) =>
      me.role === "agent" || t.owner === username;
    // Requesters never see internal AI triage (same as the backend).
    const view = (t: Ticket): Ticket =>
      me.role === "agent" ? t : { ...t, ai: null };

    if (url.pathname === "/me" && method === "GET") {
      return json(200, { username, role: me.role });
    }

    if (url.pathname === "/tickets" && method === "GET") {
      const status = url.searchParams.get("status");
      const items = tickets
        .filter(visible)
        .filter((t) => !status || t.status === status)
        .sort((a, b) => b.id - a.id);
      return json(200, { items: items.map(view), total: items.length });
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
        owner: username,
        created_at: new Date().toISOString(),
        ai: triage("other", "medium"),
      };
      tickets.push(ticket);
      return json(201, view(ticket));
    }

    const match = url.pathname.match(/^\/tickets\/(\d+)$/);
    if (match && method === "GET") {
      const ticket = tickets.find((t) => t.id === Number(match[1]));
      if (!ticket || !visible(ticket)) return problem(404, "Not found");
      return json(200, view(ticket));
    }

    const sub = url.pathname.match(/^\/tickets\/(\d+)\/(replies|draft)$/);
    if (sub) {
      const ticket = tickets.find((t) => t.id === Number(sub[1]));
      if (!ticket || !visible(ticket)) return problem(404, "Not found");
      if (sub[2] === "replies" && method === "GET") {
        const mine = replies.filter(
          (r) =>
            r.ticket_id === ticket.id &&
            (me.role === "agent" || r.status === "sent"),
        );
        return json(200, mine);
      }
      if (sub[2] === "draft" && method === "POST") {
        if (me.role !== "agent") return problem(403, "Forbidden");
        const reply: Reply = {
          id: replies.length + 1,
          ticket_id: ticket.id,
          body:
            "Express parcels delivered late get the surcharge " +
            "refunded. [delivery-delays#3]",
          citations: ["delivery-delays#3"],
          status: "draft",
          ai_generated: true,
          created_by: username,
          approved_by: null,
          created_at: new Date().toISOString(),
        };
        replies.push(reply);
        return json(201, {
          reply,
          stop_reason: "answered",
          tool_calls: ["search_kb", "get_order"],
        });
      }
    }

    const send = url.pathname.match(/^\/replies\/(\d+)\/send$/);
    if (send && method === "POST") {
      if (me.role !== "agent") return problem(403, "Forbidden");
      const reply = replies.find((r) => r.id === Number(send[1]));
      if (!reply) return problem(404, "Not found");
      if (reply.status === "sent") return problem(409, "Conflict");
      const body = JSON.parse(String(init.body ?? "{}"));
      reply.body = String(body.body ?? reply.body);
      reply.status = "sent";
      reply.approved_by = username;
      return json(200, reply);
    }

    if (match && method === "PATCH") {
      const ticket = tickets.find((t) => t.id === Number(match[1]));
      if (!ticket || !visible(ticket)) return problem(404, "Not found");
      if (me.role !== "agent") {
        return problem(403, "Forbidden", {
          detail: "Only agents can change ticket status.",
        });
      }
      const body = JSON.parse(String(init.body ?? "{}"));
      ticket.status = body.status as TicketStatus;
      return json(200, view(ticket));
    }
    return problem(404, "Not found");
  };
}
