import { Link } from "react-router";
import type { AiTriage, Ticket, TicketStatus } from "../api/types";

function AiBadge({ ai }: { ai: AiTriage }) {
  if (ai.status === "fallback") return <span>AI unavailable</span>;
  if (ai.status === "pending") return <span>AI pending</span>;
  return (
    <span>
      {ai.category} · {ai.priority}
      {ai.needs_human && <strong> · review</strong>}
    </span>
  );
}

interface Props {
  tickets: Ticket[];
  canEditStatus: boolean;
  onStatusChange: (id: number, status: TicketStatus) => void;
}

export function TicketList({
  tickets,
  canEditStatus,
  onStatusChange,
}: Props) {
  if (tickets.length === 0) return <p>No tickets match this filter.</p>;
  return (
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Title</th>
          <th>Owner</th>
          <th>Priority</th>
          <th>Status</th>
          {canEditStatus && <th>AI triage</th>}
        </tr>
      </thead>
      <tbody>
        {tickets.map((t) => (
          // `key` lets React match rows between renders efficiently.
          <tr key={t.id}>
            <td>{t.id}</td>
            <td>
              <Link to={`/tickets/${t.id}`}>{t.title}</Link>
            </td>
            <td>{t.owner}</td>
            <td>{t.priority}</td>
            <td>
              <select
                disabled={!canEditStatus}
                aria-label={`Status of ticket ${t.id}`}
                value={t.status}
                onChange={(e) =>
                  onStatusChange(t.id, e.target.value as TicketStatus)
                }
              >
                <option value="open">Open</option>
                <option value="in_progress">In progress</option>
                <option value="closed">Closed</option>
              </select>
            </td>
            {canEditStatus && <td>{t.ai && <AiBadge ai={t.ai} />}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
