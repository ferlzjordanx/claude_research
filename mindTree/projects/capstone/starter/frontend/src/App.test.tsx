import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { createMockFetch } from "./api/mockServer";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";

function renderApp(path = "/tickets") {
  const fetchImpl = createMockFetch({ latencyMs: 0 });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider fetchImpl={fetchImpl}>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

async function signIn(password = "agent-password", user = "agent") {
  await userEvent.type(screen.getByLabelText("Username"), user);
  await userEvent.type(screen.getByLabelText("Password"), password);
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("App", () => {
  it("redirects anonymous users to the login page", () => {
    renderApp("/tickets");
    expect(
      screen.getByRole("heading", { name: "Sign in" }),
    ).toBeInTheDocument();
  });

  it("shows an error for bad credentials", async () => {
    renderApp();
    await signIn("wrong");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Incorrect username or password",
    );
  });

  it("logs in, lists, creates and filters tickets", async () => {
    renderApp();
    await signIn();

    expect(
      await screen.findByText("Express parcel late"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Signed in as agent (agent)"),
    ).toBeInTheDocument();

    await userEvent.type(
      screen.getByLabelText("Title"),
      "Laptop will not boot",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create ticket" }),
    );
    expect(
      await screen.findByText("Laptop will not boot"),
    ).toBeInTheDocument();

    await userEvent.selectOptions(
      screen.getByLabelText("Filter"),
      "in_progress",
    );
    expect(
      await screen.findByText("Invoice shows wrong amount"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Express parcel late"),
    ).not.toBeInTheDocument();
  });

  it("updates a ticket status", async () => {
    renderApp();
    await signIn();
    const select = await screen.findByLabelText("Status of ticket 1");
    await userEvent.selectOptions(select, "closed");
    const row = select.closest("tr")!;
    expect(within(row).getByLabelText("Status of ticket 1")).toHaveValue(
      "closed",
    );
  });

  it("signs out", async () => {
    renderApp();
    await signIn();
    await screen.findByText("Express parcel late");
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(
      screen.getByRole("heading", { name: "Sign in" }),
    ).toBeInTheDocument();
  });

  it("requester sees own tickets, read-only status", async () => {
    renderApp();
    await signIn("alice-password", "alice");
    expect(
      await screen.findByText("Express parcel late"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Invoice shows wrong amount"),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Status of ticket 1")).toBeDisabled();
  });

  it("agent drafts an AI reply, edits it and sends it", async () => {
    renderApp();
    await signIn();
    await userEvent.click(await screen.findByText("Express parcel late"));
    expect(await screen.findByText(/confidence 90%/)).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Draft reply with AI" }),
    );
    const box = await screen.findByLabelText(/Draft/);
    expect(
      screen.getByText(/Sources: delivery-delays#3/),
    ).toBeInTheDocument();
    await userEvent.clear(box);
    await userEvent.type(box, "Refund of the surcharge is on its way.");
    await userEvent.click(
      screen.getByRole("button", { name: "Approve and send" }),
    );
    expect(await screen.findByRole("listitem")).toHaveTextContent(
      "Refund of the surcharge is on its way.",
    );
    expect(screen.queryByLabelText(/Draft/)).not.toBeInTheDocument();
  });

  it("requesters see no AI triage and no draft button", async () => {
    renderApp();
    await signIn("alice-password", "alice");
    await userEvent.click(await screen.findByText("Express parcel late"));
    expect(await screen.findByText("No replies yet.")).toBeInTheDocument();
    expect(screen.queryByText(/AI triage/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Draft reply with AI" }),
    ).not.toBeInTheDocument();
  });
});
