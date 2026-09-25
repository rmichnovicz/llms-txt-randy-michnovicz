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
  test(`guides, bundle and run details at ${width}px`, async ({ page }) => {
    const credentials = JSON.parse(fixture("seed"));
    try {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`/s/${credentials.id}#key=${credentials.token}`);
      await page
        .getByRole("button", { name: "Run details", exact: true })
        .click();
      const modal = page.getByRole("dialog", { name: "Run details" });
      await expect(modal).toBeVisible();
      await modal.getByRole("heading", { name: "Run details", exact: true }).click();
      await expect(modal).toBeVisible();
      const bounds = await modal.boundingBox();
      await page.mouse.click(bounds!.x + 4, bounds!.y + 4);
      await expect(modal).toBeVisible();
      await page.screenshot({ path: `test-results/run-details-summary-${width}.png` });
      await page.mouse.click(4, 4);
      await expect(modal).toHaveCount(0);
      const opener = page.getByRole("button", { name: "Run details", exact: true });
      await expect(opener).toBeFocused();
      await opener.click();
      await page.keyboard.press("Escape");
      await expect(modal).toHaveCount(0);
      await expect(opener).toBeFocused();
      await opener.click();
      for (const name of [
        "Selected and skipped URLs",
        "Fetch results",
        "Model usage and settings",
        "Recent jobs",
      ]) {
        await modal.getByText(name, { exact: true }).click();
      }
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
            .analyze()
        ).violations,
      ).toEqual([]);
      await page.screenshot({
        path: `test-results/run-details-${width}.png`,
        fullPage: true,
      });
      await modal.getByRole("button", { name: "Close run details" }).click();
      await page
        .getByRole("button", { name: "Guide structure", exact: true })
        .click();
      await page
        .getByLabel("Guide name", { exact: true })
        .fill("Developer docs");
      await page.getByLabel("Path scope").fill("/docs/");
      await page
        .getByLabel("Guide purpose")
        .fill("Help developers integrate the API.");
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
            .analyze()
        ).violations,
      ).toEqual([]);
      await page
        .getByRole("button", { name: "Create guide", exact: true })
        .click();
      await expect(page).toHaveURL(`/s/${credentials.id}?doc=%2Fdocs%2F`);
      const child = await page.locator("#guide-switch").inputValue();
      expect(child).not.toBe(credentials.id);
      fixture("crawl", child);
      await expect(page.locator(".document-preview")).toContainText(
        "Help developers integrate the API.",
      );
      await expect(page.locator("#guide-switch")).toHaveValue(child);
      await page.reload();
      await expect(page.locator("#guide-switch")).toHaveValue(child);
      await expect(page.locator(".document-preview")).toContainText("Help developers integrate the API.");
      await page.evaluate(() => { document.documentElement.dataset.navigationCheck = "preserved"; });
      await page.locator("#guide-switch").selectOption(credentials.id);
      await expect(page.locator("#guide-switch")).toHaveValue(credentials.id);
      await expect(page.locator("html")).toHaveAttribute("data-navigation-check", "preserved");
      await page.goBack();
      await expect(page.locator("#guide-switch")).toHaveValue(child);
      await page.goForward();
      await expect(page.locator("#guide-switch")).toHaveValue(credentials.id);
      await expect(page.locator(".document-preview")).not.toContainText(
        "Help developers integrate the API.",
      );
      await page
        .getByRole("button", { name: "Guide structure", exact: true })
        .click();
      const downloaded = page.waitForEvent("download");
      await page.getByRole("button", { name: "Download all guides" }).click();
      const download = await downloaded;
      expect(download.suggestedFilename()).toBe("llms-guides.zip");
      const archive = await download.path();
      const files = execFileSync(
        resolve("../.venv/bin/python"),
        [
          "-c",
          'import zipfile,sys; z=zipfile.ZipFile(sys.argv[1]); print(",".join(z.namelist())); assert b"docs/llms.txt" in z.read("llms.txt")',
          archive!,
        ],
        { encoding: "utf8" },
      );
      expect(files).toContain("docs/llms.txt");
      await page.getByRole("button", { name: "Check all guides" }).click();
      await expect(page.getByRole("status")).toContainText("Site check queued");
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `test-results/guide-structure-${width}.png`,
        fullPage: true,
      });
    } finally {
      fixture("cleanup", credentials.id);
    }
  });
}
