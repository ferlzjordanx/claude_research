import type { ApiClient } from "./client";
import type {
  Ticket,
  TicketCreate,
  TicketPage,
  TicketStatus,
  TokenResponse,
} from "./types";

/** Typed endpoint functions. Components never build URLs themselves. */
export function ticketsApi(client: ApiClient) {
  return {
    login: (username: string, password: string) =>
      client.request<TokenResponse>("/auth/token", {
        method: "POST",
        form: { username, password },
      }),
    list: (status: TicketStatus | "all", signal?: AbortSignal) =>
      client.request<TicketPage>(
        status === "all" ? "/tickets" : `/tickets?status=${status}`,
        { signal },
      ),
    create: (data: TicketCreate) =>
      client.request<Ticket>("/tickets", { method: "POST", body: data }),
    updateStatus: (id: number, status: TicketStatus) =>
      client.request<Ticket>(`/tickets/${id}`, {
        method: "PATCH",
        body: { status },
      }),
  };
}

export type TicketsApi = ReturnType<typeof ticketsApi>;
