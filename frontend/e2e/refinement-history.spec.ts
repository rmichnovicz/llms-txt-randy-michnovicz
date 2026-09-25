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
for (const width of [320, 1280]) {
  test(`refinement changelog survives reload at ${width}px`, async ({
    page,
  }) => {
    const { id, token } = JSON.parse(fixture("seed"));
    try {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`/s/${id}#key=${token}`);
      await expect(
        page.getByRole("button", { name: "View refinement changes" }),
      ).toHaveCount(0);
      await page
        .getByLabel("Add instructions", { exact: true })
        .fill("Prioritize API authentication for developers.");
      await page
        .getByRole("button", { name: "Save direction", exact: true })
        .click();
      await expect(
        page.getByText("Working on your brief", { exact: true }),
      ).toBeVisible();
      fixture("drain", id);
      await page
        .getByRole("button", { name: "View refinement changes" })
        .click();
      const modal = page.getByRole("dialog");
      await expect(modal).toContainText("Refinement changelog");
      await expect(modal).toContainText("These changes are already saved");
      await expect(
        modal.getByRole("group", { name: "Change summary" }),
      ).toContainText("added");
      await expect(
        modal.getByText("Directions behind this refinement (1)"),
      ).toBeVisible();
      await expect(modal.locator(".is-added")).toContainText([
        "Prioritize API authentication for developers.",
      ]);
      await expect(
        modal.getByRole("button", { name: "Use this version" }),
      ).toHaveCount(0);
      await modal
        .getByRole("button", { name: "Full documents", exact: true })
        .click();
      await expect(
        modal.getByRole("heading", { name: "Before refinement", exact: true }),
      ).toBeVisible();
      await expect(
        modal.getByLabel("Before refinement text"),
      ).not.toContainText("Prioritize API authentication");
      await expect(modal.getByLabel("Selected version text")).toContainText(
        "Prioritize API authentication",
      );
      await modal
        .getByRole("button", { name: "Changes only", exact: true })
        .click();
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
            .analyze()
        ).violations,
      ).toEqual([]);
      await page.screenshot({
        path: `test-results/refinement-${width}.png`,
        fullPage: true,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBe(true);
      await modal.getByRole("button", { name: "Done", exact: true }).click();
      await page.reload();
      await page.getByRole("button", { name: "History", exact: true }).click();
      await page.getByRole("button", { name: /Refined draft/ }).click();
      await expect(page.getByRole("dialog")).toContainText(
        "Directions behind this refinement (1)",
      );
    } finally {
      fixture("cleanup", id);
    }
  });
}
