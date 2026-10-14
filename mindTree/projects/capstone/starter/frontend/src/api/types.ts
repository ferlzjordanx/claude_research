// API models: the TypeScript mirror of the backend's OpenAPI contract.
// In larger projects generate these with `openapi-typescript`.

export type Priority = "low" | "medium" | "high";
export type TicketStatus = "open" | "in_progress" | "closed";
export type Role = "requester" | "agent";

export interface Me {
  username: string;
  role: Role;
}

export type Category =
  "delivery" | "billing" | "damage" | "account" | "other";

/** AI triage: suggestions for agents; null for requesters. */
export interface AiTriage {
  status: "pending" | "done" | "fallback";
  category: Category | null;
  priority: Priority | null;
  summary: string | null;
  confidence: number | null;
  needs_human: boolean;
}

export interface Reply {
  id: number;
  ticket_id: number;
  body: string;
  citations: string[];
  status: "draft" | "sent";
  ai_generated: boolean;
  created_by: string;
  approved_by: string | null;
  created_at: string;
}

export interface DraftResult {
  reply: Reply;
  stop_reason: string;
  tool_calls: string[];
}

export interface Ticket {
  id: number;
  title: string;
  description: string;
  priority: Priority;
  status: TicketStatus;
  owner: string;
  created_at: string;
  ai: AiTriage | null; // ISO-8601 string on the wire
}

export interface TicketCreate {
  title: string;
  description: string;
  priority: Priority;
}

export interface TicketPage {
  items: Ticket[];
  total: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

// RFC 9457 problem details returned by the backend on errors.
export interface Problem {
  title: string;
  status: number;
  detail?: string;
  request_id?: string;
  errors?: { loc: (string | number)[]; msg: string }[];
}
