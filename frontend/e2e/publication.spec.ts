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
  test(`publication and existing guide comparison at ${width}px`, async ({
    page,
    request,
  }) => {
    const { id, token } = JSON.parse(fixture("seed"));
    fixture("existing-guide", id);
    try {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`/s/${id}#key=${token}`);
      await page.getByText("Publish your guide", { exact: false }).click();
      await page
        .getByRole("button", { name: "Publish saved draft", exact: true })
        .click();
      const publicLink = page.getByRole("link", {
        name: "Open public llms.txt",
      });
      await expect(publicLink).toBeVisible();
      const publicUrl = (await publicLink.getAttribute("href"))!;
      expect(publicUrl).not.toContain(token);
      const original = await request.get(publicUrl);
      expect(original.status()).toBe(200);
      expect(original.headers()["content-type"]).toContain("text/plain");
      const publishedText = await original.text();
      await page.getByRole("button", { name: "Markdown", exact: true }).click();
      await page
        .getByLabel("Document Markdown")
        .fill("# Private changes\n\nThis is a newer draft.");
      await expect(
        page.getByRole("button", { name: "Publish updated draft" }),
      ).toBeDisabled();
      await page
        .getByRole("button", { name: "Save changes", exact: true })
        .click();
      await expect(
        page.getByText("Draft has changes", { exact: true }),
      ).toBeVisible();
      expect(await (await request.get(publicUrl)).text()).toBe(publishedText);
      await page.getByText("Existing website guide", { exact: false }).click();
      await page.getByText("Compare /llms.txt", { exact: true }).click();
      await expect(page.getByLabel("Existing guide text")).toContainText(
        "An older overview",
      );
      await expect(page.getByLabel("Draft comparison text")).toContainText(
        "Private changes",
      );
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBe(true);
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
            .analyze()
        ).violations,
      ).toEqual([]);
      await page.screenshot({
        path: `test-results/publication-${width}.png`,
        fullPage: true,
      });
      await page.getByRole("button", { name: "Publish updated draft" }).click();
      await expect(
        page.getByText("Draft has changes", { exact: true }),
      ).toHaveCount(0);
      expect(await (await request.get(publicUrl)).text()).toContain(
        "Private changes",
      );
      await page
        .getByRole("button", { name: "Unpublish", exact: true })
        .click();
      await expect(publicLink).toHaveCount(0);
      expect((await request.get(publicUrl)).status()).toBe(404);
    } finally {
      fixture("cleanup", id);
    }
  });
}

test("change inbox filters preserve review context", async ({ page }) => {
  const { id, token } = JSON.parse(fixture("seed"));
  try {
    await page.goto(`/s/${id}#key=${token}`);
    const inbox = page.getByRole("region", { name: "Change inbox" });
    await expect(inbox).toContainText("No pending changes");
    await page.getByRole("button", { name: "Check now", exact: true }).click();
    fixture("crawl", id, "A changed API page.");
    await expect(
      inbox.getByRole("button", { name: "Modified (1)", exact: true }),
    ).toBeVisible();
    await inbox.getByRole("button", { name: "Added (0)", exact: true }).click();
    await expect(inbox).toContainText("No source changes match this filter");
    await inbox
      .getByRole("button", { name: "Modified (1)", exact: true })
      .click();
    await inbox.locator(".source-change summary").click();
    await expect(inbox.getByLabel("Source diff: API reference")).toContainText(
      "A changed API page",
    );
  } finally {
    fixture("cleanup", id);
  }
});
