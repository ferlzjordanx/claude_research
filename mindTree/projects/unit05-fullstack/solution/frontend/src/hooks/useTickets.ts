import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";
import type { Ticket, TicketCreate, TicketStatus } from "../api/types";
import { useAuth } from "../auth/AuthContext";

// A discriminated union makes impossible states unrepresentable:
// you cannot have data AND an error AND loading at the same time.
export type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; tickets: Ticket[] };

export function useTickets(filter: TicketStatus | "all") {
  const { api } = useAuth();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    api
      .list(filter, controller.signal)
      .then((page) => setState({ kind: "ready", tickets: page.items }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return; // stale request: ignore
        const message =
          err instanceof ApiError ? err.message : "Unexpected error";
        setState({ kind: "error", message });
      });
    // Cleanup runs when filter changes or the component unmounts, so a
    // slow old response can never overwrite newer data.
    return () => controller.abort();
  }, [api, filter, reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  const create = useCallback(
    async (data: TicketCreate) => {
      const ticket = await api.create(data);
      setState((s) =>
        s.kind === "ready" ? { ...s, tickets: [ticket, ...s.tickets] } : s,
      );
      return ticket;
    },
    [api],
  );

  const updateStatus = useCallback(
    async (id: number, status: TicketStatus) => {
      const updated = await api.updateStatus(id, status);
      setState((s) =>
        s.kind === "ready"
          ? {
              ...s,
              tickets: s.tickets.map((t) => (t.id === id ? updated : t)),
            }
          : s,
      );
    },
    [api],
  );

  return { state, reload, create, updateStatus };
}
