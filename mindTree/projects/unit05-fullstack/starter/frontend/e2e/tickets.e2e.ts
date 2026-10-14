import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page, user: string) {
  await page.goto("/login");
  await page.getByLabel("Username").fill(user);
  await page.getByLabel("Password").fill(`${user}-password`);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(`Signed in as ${user}`)).toBeVisible();
}

test("requester creates a ticket; agent resolves it", async ({
  browser,
}) => {
  const title = `Laptop fan noise ${Date.now()}`;

  // 1. Requester (alice) files a ticket through the real API.
  const alice = await browser.newPage();
  await signIn(alice, "alice");
  await alice.getByLabel("Title").fill(title);
  await alice.getByRole("button", { name: "Create ticket" }).click();
  const aliceRow = alice.getByRole("row").filter({ hasText: title });
  await expect(aliceRow).toBeVisible();
  // The UI disables what the API would reject anyway (403).
  await expect(aliceRow.getByRole("combobox")).toBeDisabled();

  // 2. Another requester (bob) cannot see it: object-level authz.
  const bob = await browser.newPage();
  await signIn(bob, "bob");
  await expect(
    bob.getByText("No tickets match this filter."),
  ).toBeVisible();
  await expect(bob.getByText(title)).toHaveCount(0);

  // 3. Agent sees every ticket and closes alice's.
  const agent = await browser.newPage();
  await signIn(agent, "agent");
  const agentRow = agent.getByRole("row").filter({ hasText: title });
  await agentRow.getByRole("combobox").selectOption("closed");
  await expect(agentRow.getByRole("combobox")).toHaveValue("closed");

  // 4. Alice sees the new status after a reload (persisted server-side).
  await alice.getByLabel("Filter").selectOption("closed");
  await expect(
    alice.getByRole("row").filter({ hasText: title }),
  ).toBeVisible();
});

// TODO(10): remove .fixme once TODO 5-7 are done.
test.fixme("API responses carry the request ID the SPA sent", async ({
  page,
}) => {
  const response = page.waitForResponse((r) => r.url().endsWith("/me"));
  await signIn(page, "agent");
  const me = await response;
  const sent = me.request().headers()["x-request-id"];
  expect(sent).toMatch(/^[0-9a-f]{32}$/);
  expect(me.headers()["x-request-id"]).toBe(sent);
});
