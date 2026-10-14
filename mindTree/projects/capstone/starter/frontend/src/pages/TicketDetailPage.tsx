import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { ApiError } from "../api/client";
import type { DraftResult, Reply, Ticket } from "../api/types";
import { useAuth } from "../auth/AuthContext";

type Load =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; ticket: Ticket; replies: Reply[] };

function message(err: unknown): string {
  if (err instanceof ApiError) {
    return err.requestId
      ? `${err.message} (ref ${err.requestId})`
      : err.message;
  }
  return "Unexpected error";
}

export function TicketDetailPage() {
  const { id } = useParams();
  const ticketId = Number(id);
  const { api, role } = useAuth();
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [draft, setDraft] = useState<DraftResult | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api.get(ticketId, controller.signal),
      api.replies(ticketId, controller.signal),
    ])
      .then(([ticket, replies]) =>
        setLoad({ kind: "ready", ticket, replies }),
      )
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setLoad({ kind: "error", message: message(err) });
        }
      });
    return () => controller.abort();
  }, [api, ticketId]);

  async function requestDraft() {
    setBusy(true);
    setActionError(null);
    try {
      const result = await api.draft(ticketId);
      setDraft(result);
      setText(result.reply.body);
    } catch (err) {
      setActionError(message(err));
    } finally {
      setBusy(false);
    }
  }

  async function approveAndSend() {
    if (!draft) return;
    setBusy(true);
    setActionError(null);
    try {
      // TODO(9): send the (edited) text with api.send, append the sent
      // reply to the list and clear the draft.
      void text;
    } catch (err) {
      setActionError(message(err));
    } finally {
      setBusy(false);
    }
  }

  if (load.kind === "loading") return <p aria-busy="true">Loading…</p>;
  if (load.kind === "error") return <p role="alert">{load.message}</p>;
  const { ticket, replies } = load;
  const sent = replies.filter((r) => r.status === "sent");

  return (
    <main>
      <Link to="/tickets">← All tickets</Link>
      <h1>
        #{ticket.id} {ticket.title}
      </h1>
      <p>{ticket.description}</p>
      <p>
        Status: {ticket.status} · Priority: {ticket.priority} · Owner:{" "}
        {ticket.owner}
      </p>
      {ticket.ai && ticket.ai.status === "done" && (
        <section aria-label="AI triage">
          <h2>AI triage (suggestion)</h2>
          <p>
            {ticket.ai.category} · {ticket.ai.priority} · confidence{" "}
            {Math.round((ticket.ai.confidence ?? 0) * 100)}%
          </p>
          <p>{ticket.ai.summary}</p>
        </section>
      )}

      <h2>Replies</h2>
      {sent.length === 0 && <p>No replies yet.</p>}
      <ul>
        {sent.map((r) => (
          <li key={r.id}>{r.body}</li>
        ))}
      </ul>

      {role === "agent" && (
        <section aria-label="Reply assistant">
          {!draft && (
            <button onClick={requestDraft} disabled={busy}>
              {busy ? "Drafting…" : "Draft reply with AI"}
            </button>
          )}
          {draft && (
            <>
              <label>
                Draft (review before sending)
                <textarea
                  rows={6}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              </label>
              <p className="hint">
                Sources:{" "}
                {draft.reply.citations.length
                  ? draft.reply.citations.join(", ")
                  : "none (check carefully)"}
              </p>
              <button onClick={approveAndSend} disabled={busy || !text}>
                Approve and send
              </button>
            </>
          )}
        </section>
      )}
      {actionError && <p role="alert">{actionError}</p>}
    </main>
  );
}
