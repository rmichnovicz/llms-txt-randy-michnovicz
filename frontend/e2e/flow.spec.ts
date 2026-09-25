import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
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
async function audit(page: Page, name: string) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
    name + " fits",
  ).toBe(true);
  const clipped = await page
    .locator("button,h1,h2,h3,p,label,summary")
    .evaluateAll((elements) =>
      elements
        .filter(
          (el) => el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2,
        )
        .map((el) => el.textContent?.slice(0, 100)),
    );
  expect(clipped, name + " has no clipped text").toEqual([]);
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    result.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
    name,
  ).toEqual([]);
}
for (const width of [320, 390, 768, 1440]) {
  test(`complete real API flow at ${width}px`, async ({ page, context }) => {
    test.setTimeout(90000);
    await page.setViewportSize({
      width,
      height: width === 320 ? 568 : width === 390 ? 844 : 900,
    });
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    const button = (name: string) =>
      page.getByRole("button", { name, exact: true });
    let id = "";
    try {
      await page.goto("/");
      await audit(page, "start");
      await page.getByText("Private demo access", { exact: true }).click();
      await page.getByLabel("Creation key").fill("");
      await page.getByLabel("Website URL").fill("acme.example.com");
      await button("Create a brief").click();
      await expect(page).toHaveURL(/\/s\/[a-f0-9-]+$/);
      id = new URL(page.url()).pathname.split("/").pop()!;
      await expect(
        page.getByRole("heading", { name: "Creating your first draft" }),
      ).toBeVisible();
      await audit(page, "reading");
      fixture("fail", id);
      await expect(button("Retry")).toBeVisible();
      await audit(page, "failure");
      await button("Retry").click();
      await expect(button("Retry")).toHaveCount(0);
      fixture("crawl", id);
      await expect(page.locator(".document-preview h1")).toHaveText("Acme");
      await audit(page, "question");
      await page.evaluate(() => scrollTo(0, 0));
      await page.screenshot({
        path: `test-results/flow-${width}-question.png`,
        fullPage: true,
      });
      await page.getByText("Why this came up", { exact: true }).click();
      await expect(page.locator(".question-footer a")).toHaveCount(2);
      await page
        .getByLabel("Or answer in your own words")
        .fill(
          "Help first-time developers.\nKeep buyers in a secondary section.",
        );
      await button("Save answer").click();
      await expect(page.locator(".question-card")).toHaveCount(0);
      await audit(page, "regenerating");
      fixture("drain", id);
      await expect(page.locator(".document-preview")).toContainText(
        "Help first-time developers",
      );
      await button("Dismiss notice").click();
      await page.getByRole("tab", { name: "Decisions 1" }).focus();
      await page.keyboard.press("ArrowRight");
      await expect(page.getByRole("tab", { name: "Sources" })).toBeFocused();
      await expect(page.locator(".source")).toHaveCount(3);
      await audit(page, "sources");
      await page.getByRole("tab", { name: "Decisions 1" }).click();
      await button("Edit").click();
      await page.getByLabel("Edit decision").fill("Cancelled change");
      await button("Cancel").click();
      await button("Remove").click();
      await audit(page, "removal");
      await page.screenshot({ path: `test-results/removal-${width}.png` });
      await page.getByRole("heading", { name: "Remove this decision?" }).click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await page.mouse.click(4, 4);
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(button("Remove")).toBeFocused();
      await button("Remove").click();
      await button("Close removal").click();
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await button("Remove").click();
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(button("Remove")).toBeFocused();
      await button("Remove").click();
      await button("Keep decision").click();
      await button("Remove").click();
      await button("Remove and regenerate").click();
      await expect(page.getByRole("dialog")).toHaveCount(0);
      fixture("drain", id);
      await expect(page.locator(".document-preview")).not.toContainText(
        "Help first-time developers",
      );
      await page.getByText("Removed decisions", { exact: true }).click();
      await button("Restore decision").click();
      await expect(
        page.getByRole("tab", { name: "Decisions 1" }),
      ).toBeVisible();
      fixture("drain", id);
      await expect(page.locator(".document-preview")).toContainText(
        "Help first-time developers",
      );
      await page.getByRole("tab", { name: "Refine" }).click();
      await page
        .getByLabel("Add instructions")
        .fill(
          "We support research workflows. " +
            "More context for readers. ".repeat(12),
        );
      await page.getByLabel("Type of direction").selectOption("fact");
      await button("Save direction").click();
      await expect(page.getByLabel("Add instructions")).toHaveValue("");
      fixture("fail", id);
      await expect(button("Retry generation")).toBeVisible();
      await button("Retry generation").click();
      await expect(button("Retry generation")).toHaveCount(0);
      fixture("drain", id);
      await expect(page.locator(".document-preview")).toContainText(
        "We support research workflows.",
      );
      await button("Copy private access link").click();
      await expect
        .poll(() => page.evaluate(() => navigator.clipboard.readText()))
        .toContain(`/s/${id}#key=`);
      const download = page.waitForEvent("download");
      await button("Download llms.txt").click();
      expect((await download).suggestedFilename()).toBe("llms.txt");
      await button("Markdown").click();
      await page.getByLabel("Document Markdown").fill("# Discard me");
      await expect(button("Download llms.txt")).toBeDisabled();
      await button("Discard").click();
      await expect(page.getByLabel("Document Markdown")).not.toHaveValue(
        "# Discard me",
      );
      await page
        .getByLabel("Document Markdown")
        .fill(
          "# My edited guide\n\n" +
            "A long paragraph that remains readable. ".repeat(30),
        );
      await audit(page, "editing");
      await button("Save changes").click();
      await expect(button("Save changes")).toHaveCount(0);
      await button("Preview").click();
      await page.getByLabel("Daily checks").check();
      await expect(page.getByLabel("Daily checks")).toBeChecked();
      await page.getByLabel("Daily checks").uncheck();
      await expect(page.getByLabel("Daily checks")).not.toBeChecked();
      await button("Check now").click();
      await expect(button("Check now")).toBeDisabled();
      fixture("crawl", id, "refresh");
      await expect(button("Compare versions")).toBeVisible();
      await button("Compare versions").click();
      await audit(page, "proposal");
      await button("Keep current").click();
      await button("History").click();
      await page
        .getByRole("button", { name: /Generated draft/ })
        .last()
        .click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await audit(page, "comparison");
      await page.mouse.click(4, 4);
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(page.getByRole("button", { name: /Generated draft/ }).last()).toBeFocused();
      await page.getByRole("button", { name: /Generated draft/ }).last().click();
      await page.screenshot({
        path: `test-results/flow-${width}-comparison.png`,
        fullPage: true,
      });
      const controls = page.getByRole("dialog").getByRole("button");
      await controls.last().focus();
      await page.keyboard.press("Tab");
      await expect(controls.first()).toBeFocused();
      await button("Close comparison").click();
      await page
        .getByRole("button", { name: /Generated draft/ })
        .last()
        .click();
      await button("Keep current").click();
      await page
        .getByRole("button", { name: /Generated draft/ })
        .last()
        .click();
      await button("Use this version").click();
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await button("Preview").click();
      await expect(page.locator(".document-preview h1")).toHaveText("Acme");
      await audit(page, "restored");
    } finally {
      if (id) fixture("cleanup", id);
    }
  });
}

test("private-link recovery, errors, source notes and long text at enlarged scale", async ({
  page,
  context,
}) => {
  const { id, token } = JSON.parse(fixture("seed"));
  try {
    await page.setViewportSize({ width: 640, height: 900 });
    await page.goto(`/s/${id}`);
    await expect(page.getByLabel("Private access link")).toBeVisible();
    await page.getByLabel("Private access link").fill("not a link");
    await page.getByRole("button", { name: "Open workspace" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "Paste the full private access link",
    );
    await audit(page, "recovery");
    await page
      .getByLabel("Private access link")
      .fill(`http://127.0.0.1:5175/s/${id}#key=${token}`);
    await page.getByRole("button", { name: "Open workspace" }).click();
    await expect(page.locator(".document-preview h1")).toHaveText("Acme");
    await page.route(`**/api/projects/${id}/document`, async (route) => {
      const response = await route.fetch();
      const data = await response.json();
      data.snapshot.warnings = [
        {
          url:
            "https://acme.example.com/" + "very-long-resource-name-".repeat(18),
          reason:
            "This page was temporarily unavailable. The previous source was retained.",
        },
      ];
      data.questions[0].data.question =
        "Which audience should guide the next version when both implementation details and buying criteria matter equally?";
      data.questions[0].data.options = [
        "Prioritize implementation details for a distributed team building its first integration, while retaining a clearly labeled path to commercial and procurement information.",
        "Keep both audiences equally represented and organize each section by the tasks readers need to complete.",
      ];
      data.questions[0].data.rationale =
        "The website serves several audiences. " +
        "This choice changes the order and prominence of the linked resources. ".repeat(
          4,
        );
      await route.fulfill({ response, json: data });
    });
    await page.reload();
    await expect(page.locator(".question-card")).toContainText(
      "distributed team",
    );
    await page.evaluate(() => {
      document.documentElement.style.zoom = "2";
    });
    await audit(page, "200 percent scale");
    await page.screenshot({
      path: "test-results/flow-zoom.png",
      fullPage: true,
    });
    await page.getByRole("tab", { name: "Sources" }).click();
    await page.getByText("1 crawl notes", { exact: true }).click();
    await expect(page.locator(".warnings")).toContainText(
      "temporarily unavailable",
    );
    await audit(page, "long source notes");
    await page.getByRole("tab", { name: "Refine" }).click();
    await page.route(`**/api/projects/${id}/questions`, (route) =>
      route.fulfill({
        status: 503,
        json: { detail: "The service is temporarily unavailable. Try again." },
      }),
    );
    await page.getByRole("button", { name: "Ask me another question" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "temporarily unavailable",
    );
    await page.getByRole("button", { name: "Dismiss error" }).click();
    await expect(page.getByRole("alert")).toHaveCount(0);
    await page.getByRole("link", { name: "Brief home" }).click();
    await expect(page.getByLabel("Website URL")).toBeVisible();
    await page.getByLabel("Website URL").fill("http://127.0.0.1");
    await page.getByRole("button", { name: "Create a brief" }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    await audit(page, "invalid URL");
  } finally {
    fixture("cleanup", id);
  }
});

for (const option of [
  "Teams evaluating Acme",
  "Both, with a short path for each",
]) {
  test(`select option: ${option}`, async ({ page }) => {
    const { id, token } = JSON.parse(fixture("seed"));
    try {
      await page.goto(`/s/${id}#key=${token}`);
      await page.getByRole("button", { name: option, exact: true }).click();
      await expect(page.locator(".question-card")).toHaveCount(0);
      fixture("drain", id);
      await expect(page.locator(".document-preview")).toContainText(option);
    } finally {
      fixture("cleanup", id);
    }
  });
}
