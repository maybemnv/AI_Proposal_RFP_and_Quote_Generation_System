import {expect, test} from "./fixture";
import type {APIRequestContext} from "@playwright/test";
import {readFile} from "node:fs/promises";

async function lockNorthwindProposal(request: APIRequestContext) {
  const apiUrl = "http://localhost:8106";
  const quote = {
    currency: "USD", discountMinor: 0, taxMinor: 0,
    lines: [
      {id: "line-strategy", label: "Strategy days", ruleId: "rule_strategy_day", quantity: 4, optional: false, selected: true, sourceRecordIds: []},
      {id: "line-optional-migration", label: "Content migration", ruleId: "rule_content_migration", quantity: 1, optional: true, selected: true, sourceRecordIds: []},
      {id: "line-optional-training", label: "Training session", ruleId: "rule_training", quantity: 1, optional: true, selected: false, sourceRecordIds: []},
    ],
    installments: [
      {sequence: 1, label: "Mobilization", amountMinor: 411000, dueDescription: "Within 3 business days"},
      {sequence: 2, label: "Acceptance", amountMinor: 249000, dueDescription: "After workbook sign-off"},
    ],
  };
  expect((await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/scope/resolve`, {
    data: {openQuestion: "req_legacy_cms", resolution: "Legacy CMS stays on v4 through Q4."},
  })).ok()).toBeTruthy();
  expect((await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/quote/calculate`, {data: quote})).ok()).toBeTruthy();
  expect((await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/generate`, {data: {
    templateId: "tmpl-consulting-v1", requestedSections: ["scope", "case_studies"],
    modelProvider: "claude", modelName: "claude-opus-5",
  }})).ok()).toBeTruthy();
  const validated = await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/validate`);
  expect((await validated.json()).flags.filter((flag: {severity: string}) => flag.severity === "blocking")).toEqual([]);
  const submitted = await request.post(`${apiUrl}/v1/proposal-versions/version_northwind/submit`);
  const approvals = (await submitted.json()).approvals as {id: string; requiredRole: string}[];
  for (const approval of approvals) {
    const decided = await request.post(`${apiUrl}/v1/approvals/${approval.id}/decide`, {data: {
      decision: "approved", reviewerId: `user-${approval.requiredRole}`, reviewerRole: approval.requiredRole,
    }});
    expect(decided.ok(), await decided.text()).toBeTruthy();
  }
  return (await request.get(`${apiUrl}/v1/proposal-versions/version_northwind`)).json();
}

async function prepareRfpProposal(request: APIRequestContext) {
  const apiUrl = "http://localhost:8106";
  const versionId = "version_rfp_response";
  const quote = {
    currency: "USD", discountMinor: 0, taxMinor: 0,
    lines: [{id: "line-rfp", label: "Response days", ruleId: "rule_strategy_day", quantity: 2, optional: false, selected: true, sourceRecordIds: ["src-rfp-response"]}],
    installments: [
      {sequence: 1, label: "Mobilization", amountMinor: 133000, dueDescription: "On authority to proceed"},
      {sequence: 2, label: "Workbook acceptance", amountMinor: 107000, dueDescription: "Within ten working days of review"},
    ],
  };
  expect((await request.post(`${apiUrl}/v1/proposal-versions/${versionId}/quote/calculate`, {data: quote})).ok()).toBeTruthy();
  expect((await request.post(`${apiUrl}/v1/proposal-versions/${versionId}/generate`, {data: {
    templateId: "tpl-rfp", requestedSections: ["rfp_answers", "pricing"],
    modelProvider: "claude", modelName: "claude-opus-5",
  }})).ok()).toBeTruthy();
  const validated = await request.post(`${apiUrl}/v1/proposal-versions/${versionId}/validate`);
  expect((await validated.json()).flags.filter((flag: {severity: string}) => flag.severity === "blocking")).toEqual([]);
  const submitted = await request.post(`${apiUrl}/v1/proposal-versions/${versionId}/submit`);
  expect(submitted.ok()).toBeTruthy();
  const approvals = (await submitted.json()).approvals as {id: string; requiredRole: string}[];
  for (const approval of approvals) {
    expect((await request.post(`${apiUrl}/v1/approvals/${approval.id}/decide`, {data: {
      decision: "approved", reviewerId: `user-${approval.requiredRole}`, reviewerRole: approval.requiredRole,
    }})).ok()).toBeTruthy();
  }
  expect((await request.post(`${apiUrl}/v1/proposal-versions/${versionId}/render`, {data: {}})).ok()).toBeTruthy();
  return (await request.get(`${apiUrl}/v1/proposal-versions/${versionId}`)).json();
}

test("preview section order matches the PDF section order", async ({page, request}) => {
  await lockNorthwindProposal(request);
  await page.goto("/proposals/prop_northwind/preview");
  await expect(page.getByRole("heading", {level: 2}).first()).toBeVisible();
  const headings = await page.getByRole("heading", {level: 2}).allTextContents();
  expect(headings).toEqual(["Executive summary", "Understanding", "Scope", "Milestones",
    "Assumptions", "Options", "Pricing", "Payment schedule", "Case studies", "Next steps"]);
});

test("optional services expose each line and selection without changing the headline total", async ({page, request}) => {
  const version = await lockNorthwindProposal(request);
  await page.goto("/proposals/prop_northwind/preview");
  const optionalLines = version.quote.lines.filter((line: {optional: boolean}) => line.optional);
  const optionRows = page.getByTestId("optional-line");
  await expect(optionRows).toHaveCount(optionalLines.length);
  for (const line of optionalLines) {
    const row = optionRows.filter({hasText: line.label});
    await expect(row).toHaveAttribute("data-selected", String(line.selected));
    await expect(row).toHaveAttribute("data-minor", String(line.subtotalMinor));
  }
  await expect(page.getByTestId("total-minor")).toHaveAttribute("data-minor", String(version.quote.totalMinor));
});

test("download is the server-rendered PDF", async ({page, request}) => {
  await lockNorthwindProposal(request);
  await page.goto("/proposals/prop_northwind/preview");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", {name: "Download PDF"}).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  const path = await download.path();
  expect(path).not.toBeNull();
  const bytes = await readFile(path!);
  expect(bytes.subarray(0, 4).toString("ascii")).toBe("%PDF");
  expect(bytes.length).toBeGreaterThan(1_000);
});

test("preview uses the selected RFP version and quote", async ({page, request}) => {
  const version = await prepareRfpProposal(request);

  await page.goto("/proposals/prop_rfp_response/preview");
  const document = page.locator(".proposal-document");
  await expect(document.getByRole("heading", {level: 1})).toHaveText(version.title);
  await expect(document.getByRole("heading", {name: "RFP answers"})).toBeVisible();
  const rfpSection = version.sections.find((section: {key: string}) => section.key === "rfp_answers");
  expect(rfpSection).toBeDefined();
  const firstAnswer = rfpSection!.blocks[0].content;
  await expect(document.getByText(firstAnswer)).toBeVisible();
  await expect(page.getByTestId("total-minor")).toHaveAttribute("data-minor", String(version.quote.totalMinor));
  await expect(page.getByTestId("installment").filter({hasText: version.quote.paymentSchedule[0].label})).toContainText(version.quote.paymentSchedule[0].dueDescription);
});

test("preview reports a failed download instead of claiming success", async ({page, request}) => {
  await prepareRfpProposal(request);
  await page.route("**/v1/documents/*/download", (route) => route.fulfill({
    status: 502,
    contentType: "application/json",
    body: JSON.stringify({flags: [{code: "RENDER_ERROR", severity: "blocking", message: "download failed"}]}),
  }));

  await page.goto("/proposals/prop_rfp_response/preview");
  await page.getByRole("button", {name: "Download PDF"}).click();
  await expect(page.getByText("download failed")).toBeVisible();
  await expect(page.locator(".status-downloaded")).not.toBeVisible();
});
