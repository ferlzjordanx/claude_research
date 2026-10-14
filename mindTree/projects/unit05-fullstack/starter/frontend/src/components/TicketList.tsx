import type { Ticket, TicketStatus } from "../api/types";

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
  void canEditStatus;
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
        </tr>
      </thead>
      <tbody>
        {tickets.map((t) => (
          // `key` lets React match rows between renders efficiently.
          <tr key={t.id}>
            <td>{t.id}</td>
            <td>{t.title}</td>
            <td>{t.owner}</td>
            <td>{t.priority}</td>
            <td>
              {/* TODO(9): disable for users who cannot edit status */}
              <select
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
          </tr>
        ))}
      </tbody>
    </table>
  );
}
