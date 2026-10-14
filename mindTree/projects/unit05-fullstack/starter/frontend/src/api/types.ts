// API models: the TypeScript mirror of the backend's OpenAPI contract.
// In larger projects generate these with `openapi-typescript`.

export type Priority = "low" | "medium" | "high";
export type TicketStatus = "open" | "in_progress" | "closed";
export type Role = "requester" | "agent";

export interface Me {
  username: string;
  role: Role;
}

export interface Ticket {
  id: number;
  title: string;
  description: string;
  priority: Priority;
  status: TicketStatus;
  owner: string;
  created_at: string; // ISO-8601 string on the wire
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
