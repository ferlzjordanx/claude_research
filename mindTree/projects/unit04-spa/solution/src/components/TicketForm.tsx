import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import type { Priority, TicketCreate } from "../api/types";

interface Props {
  onSubmit: (data: TicketCreate) => Promise<unknown>;
}

type FieldErrors = Partial<Record<keyof TicketCreate, string>>;

export function validate(data: TicketCreate): FieldErrors {
  const errors: FieldErrors = {};
  const title = data.title.trim();
  if (title.length < 3 || title.length > 120) {
    errors.title = "Title must be 3-120 characters.";
  }
  if (data.description.length > 2000) {
    errors.description = "Description must be at most 2000 characters.";
  }
  return errors;
}

/** Controlled form: React state is the single source of truth. */
export function TicketForm({ onSubmit }: Props) {
  const [values, setValues] = useState<TicketCreate>({
    title: "",
    description: "",
    priority: "medium",
  });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function update<K extends keyof TicketCreate>(
    key: K,
    value: TicketCreate[K],
  ) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    // Client-side validation is for fast feedback; the server
    // validates again because the client can be bypassed.
    const clientErrors = validate(values);
    setErrors(clientErrors);
    setFormError(null);
    if (Object.keys(clientErrors).length > 0) return;

    setSubmitting(true);
    try {
      await onSubmit({ ...values, title: values.title.trim() });
      setValues({ title: "", description: "", priority: "medium" });
    } catch (err) {
      if (err instanceof ApiError && err.problem.errors) {
        // Map server-side field errors back onto the form fields.
        const serverErrors: FieldErrors = {};
        for (const e of err.problem.errors) {
          const field = e.loc[e.loc.length - 1] as keyof TicketCreate;
          serverErrors[field] = e.msg;
        }
        setErrors(serverErrors);
      } else {
        setFormError(err instanceof Error ? err.message : "Request failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} aria-label="New ticket" noValidate>
      <label>
        Title
        <input
          value={values.title}
          onChange={(e) => update("title", e.target.value)}
          aria-invalid={Boolean(errors.title)}
        />
      </label>
      {errors.title && <p role="alert">{errors.title}</p>}
      <label>
        Description
        <textarea
          value={values.description}
          onChange={(e) => update("description", e.target.value)}
        />
      </label>
      {errors.description && <p role="alert">{errors.description}</p>}
      <label>
        Priority
        <select
          value={values.priority}
          onChange={(e) => update("priority", e.target.value as Priority)}
        >
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
      </label>
      {formError && <p role="alert">{formError}</p>}
      <button type="submit" disabled={submitting}>
        {submitting ? "Saving…" : "Create ticket"}
      </button>
    </form>
  );
}
