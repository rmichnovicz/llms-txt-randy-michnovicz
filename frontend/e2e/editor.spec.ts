import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
const root = resolve("..");
function fixture(...args: string[]) {
  return execFileSync(
    resolve(root, ".venv/bin/python"),
    [resolve(root, "tests/ui_fixture.py"), ...args],
    { cwd: root, encoding: "utf8" },
  );
}
let credentials: { id: string; token: string };
test.beforeEach(async ({ page }) => {
  credentials = JSON.parse(fixture("seed"));
  await page.goto(`/s/${credentials.id}#key=${credentials.token}`);
  await expect(
    page.getByRole("heading", { name: "Your llms.txt" }),
  ).toBeVisible();
});
test.afterEach(() => {
  fixture("cleanup", credentials.id);
});
test("question answer, decision edit and removal regenerate the visible document", async ({
  page,
}) => {
  await expect(
    page.getByRole("heading", { name: "Who should this guide help first?" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Developers integrating Acme" })
    .click();
  await expect(page.getByRole("status")).toContainText("Direction saved");
  fixture("drain", credentials.id);
  await expect(page.locator(".document-preview")).toContainText(
    "Answer: Developers integrating Acme",
  );
  await page.getByRole("tab", { name: "Decisions 1" }).click();
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await page
    .getByLabel("Edit decision")
    .fill("Focus on teams evaluating Acme.");
  await page.getByRole("button", { name: "Save and update" }).click();
  await expect(page.getByLabel("Edit decision")).toHaveCount(0);
  fixture("drain", credentials.id);
  await expect(page.locator(".document-preview")).toContainText(
    "Focus on teams evaluating Acme.",
  );
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await page.getByRole("button", { name: "Remove and regenerate" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  fixture("drain", credentials.id);
  await expect(page.locator(".document-preview")).not.toContainText(
    "Focus on teams evaluating Acme.",
  );
  await page.getByText("Removed decisions", { exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Restore decision" }),
  ).toBeVisible();
});
test("manual edits save and history restores the earlier document", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  await page
    .getByLabel("Document Markdown")
    .fill("# My custom guide\n\nHandwritten context.");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Changes saved");
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "My custom guide" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: /Generated draft/ }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Use this version" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await expect(page.locator(".document-preview h1")).toHaveText("Acme");
});
test("dismiss and continued interview leave document intact", async ({
  page,
}) => {
  const before = await page.locator(".document-preview").textContent();
  await page.getByRole("button", { name: "Dismiss", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Who should this guide help first?" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Ask me another question" }).click();
  await expect(
    page.getByRole("button", { name: "Ask me another question" }),
  ).toBeDisabled();
  fixture("drain", credentials.id);
  await expect(page.locator(".muted-note")).toContainText(
    "No consequential questions",
  );
  expect(await page.locator(".document-preview").textContent()).toBe(before);
});
test("private link becomes a cookie and mobile layout fits", async ({
  page,
}) => {
  await expect(page).toHaveURL(`/s/${credentials.id}`);
  const cookies = await page.context().cookies();
  expect(cookies.some((c) => c.name.startsWith("brief_") && c.httpOnly)).toBe(
    true,
  );
  await page.screenshot({
    path: "test-results/workspace-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/workspace-mobile.png",
    fullPage: true,
  });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Your llms.txt" }),
  ).toBeVisible();
});
test("preview treats embedded HTML as text-free markup, not executable content", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  await page
    .getByLabel("Document Markdown")
    .fill(
      "# Safe title\n\n<script>window.injected=true</script>\n\n[click](javascript:alert(1))",
    );
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  expect(
    await page.evaluate(() => Reflect.get(window, "injected")),
  ).toBeUndefined();
  expect(
    await page.locator(".document-preview a").getAttribute("href"),
  ).not.toContain("javascript:");
});
