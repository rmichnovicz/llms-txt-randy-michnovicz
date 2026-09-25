import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
function fixture(...args: string[]) {
  return execFileSync(
    resolve("../.venv/bin/python"),
    [resolve("../tests/ui_fixture.py"), ...args],
    { encoding: "utf8" },
  );
}
for (const resolution of [
  "Keep my answer",
  "Revise answer",
  "Remove my override",
]) {
  test(`changed evidence review: ${resolution}`, async ({ page }) => {
    const credentials = JSON.parse(fixture("seed"));
    try {
      await page.setViewportSize({
        width: resolution === "Revise answer" ? 320 : 1280,
        height: 900,
      });
      await page.goto(`/s/${credentials.id}#key=${credentials.token}`);
      await page
        .getByRole("button", { name: "Developers integrating Acme" })
        .click();
      await expect(page.getByRole("status")).toContainText("Direction saved");
      fixture("drain", credentials.id);
      await expect(page.locator(".document-preview")).toContainText(
        "Developers integrating Acme",
      );
      await page
        .getByRole("button", { name: "Check now", exact: true })
        .click();
      await expect(
        page.getByRole("button", { name: "Check now", exact: true }),
      ).toBeDisabled();
      fixture("crawl", credentials.id, " Changed authentication instructions.");
      const inbox = page.getByRole("region", { name: "Change inbox" });
      await expect(inbox).toBeVisible();
      await inbox.locator(".source-change summary").click();
      await expect(page.getByLabel("Source diff: API reference")).toContainText(
        "Changed authentication instructions",
      );
      await expect(inbox).toContainText("Linked from: Start building");
      await page.getByRole("button", { name: "Inspect proposed edit" }).click();
      await expect(
        page.getByRole("button", { name: "Use this version" }),
      ).toBeDisabled();
      await page.getByRole("button", { name: "Close comparison" }).click();
      const card = page.getByRole("article", { name: "Review saved answer" });
      await expect(card).toBeVisible();
      await card.getByText("Compare the evidence", { exact: true }).click();
      await expect(
        card.getByText("Latest website evidence", { exact: true }),
      ).toBeVisible();
      await expect(card).toContainText("Changed authentication instructions");
      await expect(page.locator(".document-preview")).toContainText(
        "Developers integrating Acme",
      );
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
            .analyze()
        ).violations,
      ).toEqual([]);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `test-results/review-${resolution.replaceAll(" ", "-")}.png`,
        fullPage: true,
      });
      await card.getByRole("button", { name: resolution, exact: true }).click();
      if (resolution === "Revise answer") {
        await page
          .getByLabel("Edit decision")
          .fill("Help developers using the updated API.");
        await page
          .getByRole("button", { name: "Save and update", exact: true })
          .click();
      }
      await expect(page.getByRole("status")).toContainText("Direction saved");
      // The old proposal must never appear to be the result of this new answer.
      await expect(
        page.getByText("A new version is ready to review.", { exact: true }),
      ).toHaveCount(0);
      await expect(
        page.getByText("Preparing a document with your latest decisions.", {
          exact: false,
        }),
      ).toBeVisible();
      if (resolution === "Keep my answer") {
        fixture("fail", credentials.id);
        await expect(
          page.getByRole("button", { name: "Retry", exact: true }),
        ).toBeVisible();
        await expect(
          page.getByText("A new version is ready to review.", { exact: true }),
        ).toHaveCount(0);
        await page.getByRole("button", { name: "Retry", exact: true }).click();
        await expect(
          page.getByRole("button", { name: "Retry", exact: true }),
        ).toHaveCount(0);
      }
      fixture("drain", credentials.id);
      await page.getByRole("tab", { name: "Refine", exact: true }).click();
      await expect(card).toHaveCount(0);
      await expect(page.locator(".document-preview")).toContainText(
        "Developers integrating Acme",
      );
      await page.getByRole("button", { name: "Inspect proposed edit" }).click();
      await expect(page.getByLabel("Proposed document diff")).toBeVisible();
      await expect(page.getByLabel("Change summary")).toBeVisible();
      await page
        .getByRole("button", { name: "Full documents", exact: true })
        .click();
      await expect(page.getByLabel("Current draft text")).toBeVisible();
      await expect(page.getByLabel("Selected version text")).toBeVisible();
      await page
        .getByRole("button", { name: "Changes only", exact: true })
        .click();
      await expect(page.getByLabel("Proposed document diff")).toBeVisible();
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
            .analyze()
        ).violations,
      ).toEqual([]);
      await page.screenshot({
        path: `test-results/changes-modal-${resolution.replaceAll(" ", "-")}.png`,
      });

      await page.getByRole("button", { name: "Close comparison" }).click();
      await page.getByRole("button", { name: "Test proposed update" }).click();
      await expect(page.getByLabel("Version to test")).toHaveValue("proposal");
      await page.getByRole("button", { name: "Run suggested tests" }).click();
      await expect(
        page.getByRole("article", { name: "Reader test results" }),
      ).toContainText("queued");
      fixture("evaluate", credentials.id);
      await expect(
        page.getByRole("article", { name: "Reader test results" }),
      ).toContainText("Expected source cited");
      await page.getByRole("button", { name: "Inspect proposed edit" }).click();
      await page.getByRole("button", { name: "Use this version" }).click();
      await expect(
        page.getByRole("region", { name: "Change inbox" }),
      ).toContainText("No pending changes");
      if (resolution === "Remove my override") {
        await expect(page.locator(".document-preview")).not.toContainText(
          "Answer: Developers integrating Acme",
        );
      } else {
        await expect(page.locator(".document-preview")).toContainText(
          resolution === "Revise answer"
            ? "updated API"
            : "Developers integrating Acme",
        );
      }
    } finally {
      fixture("cleanup", credentials.id);
    }
  });
}
