import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { TicketForm, validate } from "./TicketForm";

describe("validate", () => {
  it("rejects short titles", () => {
    expect(
      validate({ title: " ab ", description: "", priority: "low" }).title,
    ).toBeDefined();
  });
});

describe("TicketForm", () => {
  it("shows a validation error and does not submit", async () => {
    const onSubmit = vi.fn();
    render(<TicketForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Title"), "ab");
    await userEvent.click(
      screen.getByRole("button", { name: "Create ticket" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent("3-120 characters");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits trimmed values and resets", async () => {
    const onSubmit = vi.fn(async () => undefined);
    render(<TicketForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Title"), "  Printer jam  ");
    await userEvent.selectOptions(
      screen.getByLabelText("Priority"),
      "high",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create ticket" }),
    );
    expect(onSubmit).toHaveBeenCalledWith({
      title: "Printer jam",
      description: "",
      priority: "high",
    });
    expect(screen.getByLabelText("Title")).toHaveValue("");
  });

  it("maps server field errors onto fields", async () => {
    const onSubmit = vi.fn(async () => {
      throw new ApiError(422, {
        title: "Validation failed",
        status: 422,
        errors: [{ loc: ["body", "title"], msg: "already taken" }],
      });
    });
    render(<TicketForm onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText("Title"), "Valid title");
    await userEvent.click(
      screen.getByRole("button", { name: "Create ticket" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "already taken",
    );
  });
});
