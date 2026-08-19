import {expect, test} from "./fixture";

test("Trace A clicks the demo path from capture through delivery", async ({page, request}) => {
  const successfulMutations: string[] = [];
  page.on("response", (response) => {
    const request = response.request();
    if (request.method() !== "GET" && response.ok() && response.url().startsWith("http://localhost:8106/v1/")) {
      successfulMutations.push(new URL(response.url()).pathname);
    }
  });

  await page.goto("/opportunities");
  await page.getByRole("button", {name: "Import"}).click();
  await expect(page.getByRole("row", {name: /Northwind Retail Group/})).toBeVisible();
  await page.getByLabel("Outcome").selectOption("failure");
  await page.getByRole("button", {name: "Import"}).click();
  await expect(page.getByText("AUTH")).toBeVisible();

  await page.goto("/proposals/prop_northwind");
  await page.getByTestId("source-chip").first().click();
  await expect(page.getByTestId("evidence-excerpt")).toBeVisible();

  await page.goto("/proposals/prop_northwind/scope");
  await page.getByTestId("resolve-open-question").click();
  await page.getByLabel("Resolution").fill("Legacy CMS stays on v4 through Q4.");
  await page.getByRole("button", {name: "Confirm"}).click();
  await expect(page.getByText("Scope is ready for the next gate.")).toBeVisible();

  await page.goto("/proposals/prop_northwind/quote");
  const before = await page.getByTestId("total-minor").getAttribute("data-minor");
  await page.getByTestId("line-optional-training").click();
  await expect(page.getByTestId("total-minor")).not.toHaveAttribute("data-minor", before!);
  await page.getByTestId("line-optional-training").click();
  await expect(page.getByTestId("total-minor")).toHaveAttribute("data-minor", before!);
  await page.getByLabel("Discount").fill("500.00");
  const quoteResponse = page.waitForResponse((response) =>
    response.request().method() === "POST"
      && response.url().endsWith("/v1/proposal-versions/version_northwind/quote/calculate"),
  );
  await page.getByRole("button", {name: "Recalculate"}).click();
  expect((await quoteResponse).status()).toBe(200);
  await expect(page.getByText(/review required/i)).toBeVisible();

  const apiUrl = "http://localhost:8106";
  const generated = await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/generate`, {data: {
    templateId: "tmpl-consulting-v1", requestedSections: ["scope", "case_studies"],
    modelProvider: "claude", modelName: "claude-opus-5",
  }});
  expect(generated.ok()).toBeTruthy();
  const validated = await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/validate`);
  expect(validated.ok()).toBeTruthy();
  expect((await validated.json()).flags.filter((flag: {severity: string}) => flag.severity === "blocking")).toEqual([]);
  const submitted = await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/submit`);
  expect(submitted.ok()).toBeTruthy();
  const approvals = (await submitted.json()).approvals as {id: string; kind: string; requiredRole: string}[];
  for (const approval of approvals.filter((item) => item.kind !== "proposal")) {
    const decided = await request.post(`${apiUrl}/v1/approvals/${approval.id}/decide`, {data: {
      decision: "approved", reviewerId: `user-${approval.requiredRole}`, reviewerRole: approval.requiredRole,
    }});
    expect(decided.ok()).toBeTruthy();
  }

  await page.goto("/proposals/prop_northwind/approval?as=proposal_approver");
  await page.getByTestId("approval-proposal").getByRole("button", {name: "Approve"}).click();
  await expect(page.getByText("Locked")).toBeVisible();

  await page.goto("/proposals/prop_northwind/preview");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", {name: "Download PDF"}).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  await page.goto("/analytics");
  await expect(page.getByTestId("views-chart")).toBeVisible();
  expect(successfulMutations).toEqual(expect.arrayContaining([
    "/v1/opportunities/import",
    "/v1/proposal-versions/version_northwind/scope/resolve",
    "/v1/proposal-versions/version_northwind/quote/calculate",
    expect.stringMatching(/^\/v1\/approvals\/approval[-_]/),
    "/v1/proposal-versions/version_northwind/render",
  ]));
});
