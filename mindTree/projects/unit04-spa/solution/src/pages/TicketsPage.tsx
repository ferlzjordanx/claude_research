import { useState } from "react";
import type { TicketStatus } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { TicketForm } from "../components/TicketForm";
import { TicketList } from "../components/TicketList";
import { useTickets } from "../hooks/useTickets";

export function TicketsPage() {
  const { username, logout } = useAuth();
  const [filter, setFilter] = useState<TicketStatus | "all">("all");
  const { state, reload, create, updateStatus } = useTickets(filter);
  const [actionError, setActionError] = useState<string | null>(null);

  async function changeStatus(id: number, status: TicketStatus) {
    setActionError(null);
    try {
      await updateStatus(id, status);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Update failed");
    }
  }

  return (
    <main>
      <header>
        <h1>Support tickets</h1>
        <span>Signed in as {username}</span>
        <button onClick={logout}>Sign out</button>
      </header>
      <TicketForm onSubmit={create} />
      <label>
        Filter
        <select
          value={filter}
          onChange={(e) =>
            setFilter(e.target.value as TicketStatus | "all")
          }
        >
          <option value="all">All</option>
          <option value="open">Open</option>
          <option value="in_progress">In progress</option>
          <option value="closed">Closed</option>
        </select>
      </label>
      {actionError && <p role="alert">{actionError}</p>}
      {state.kind === "loading" && <p aria-busy="true">Loading tickets…</p>}
      {state.kind === "error" && (
        <div role="alert">
          <p>Could not load tickets: {state.message}</p>
          <button onClick={reload}>Retry</button>
        </div>
      )}
      {state.kind === "ready" && (
        <TicketList tickets={state.tickets} onStatusChange={changeStatus} />
      )}
    </main>
  );
}
