import type { ApiClient } from "./client";
import type {
  DraftResult,
  Me,
  Reply,
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
    me: () => client.request<Me>("/me"),
    list: (status: TicketStatus | "all", signal?: AbortSignal) =>
      client.request<TicketPage>(
        status === "all" ? "/tickets" : `/tickets?status=${status}`,
        { signal },
      ),
    get: (id: number, signal?: AbortSignal) =>
      client.request<Ticket>(`/tickets/${id}`, { signal }),
    replies: (id: number, signal?: AbortSignal) =>
      client.request<Reply[]>(`/tickets/${id}/replies`, { signal }),
    draft: (id: number) =>
      client.request<DraftResult>(`/tickets/${id}/draft`, {
        method: "POST",
      }),
    send: (replyId: number, body: string) =>
      client.request<Reply>(`/replies/${replyId}/send`, {
        method: "POST",
        body: { body },
      }),
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
