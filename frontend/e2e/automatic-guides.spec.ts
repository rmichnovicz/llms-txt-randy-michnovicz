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
for (const width of [320, 1280])
  test(`automatic guides root-first at ${width}px`, async ({ page }) => {
    const { id, token } = JSON.parse(fixture("seed-auto"));
    try {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`/s/${id}#key=${token}`);
      const panel = page.getByRole("region", {
        name: "Automatic section guides",
      });
      await expect(panel).toContainText("Queued after the main guide");
      await expect(page.locator(".document-preview")).toContainText("Acme");
      await expect(page.locator(".draft-badge")).toHaveText("Draft");
      const href = await panel
        .getByRole("link", { name: "Open Docs" })
        .getAttribute("href");
      expect(href).toBe(`/s/${id}?doc=%2Fdocs%2F`);
      const child = (await page.locator("#guide-switch option").filter({ hasText: "Docs · /docs/" }).getAttribute("value"))!;
      await panel.getByRole("button", { name: "Cancel Docs" }).click();
      await expect(panel).toContainText("Cancelled");
      await panel.getByRole("button", { name: "Resume Docs" }).click();
      await expect(panel).toContainText("Queued after the main guide");
      fixture("crawl", child);
      await expect(panel).toContainText("Ready");
      await expect(
        page
          .locator(".document-preview")
          .getByRole("link", { name: "Docs", exact: true }),
      ).toHaveAttribute("href", "https://acme.example.com/docs/llms.txt");
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
        path: `test-results/auto-guides-${width}.png`,
        fullPage: true,
      });
      await panel.getByRole("link", { name: "Open Docs" }).click();
      await expect(page.getByLabel("Guide", { exact: true })).toHaveValue(
        child,
      );
      await expect(page.locator(".document-preview")).toContainText("Acme");
    } finally {
      fixture("cleanup", id);
    }
  });

test('older workspace responses cannot overwrite completed work', async ({page}) => {
 const {id,token}=JSON.parse(fixture('seed'));
 let release!:()=>void;
 const gate=new Promise<void>(resolve=>{release=resolve;});
 let held=false;
 try {
  await page.goto(`/s/${id}#key=${token}`);
  await expect(page.locator('.document-preview')).toContainText('Acme');
  await page.route(`**/api/projects/${id}/document`, async route=>{
   if(route.request().method()!=='GET' || held){await route.continue();return;}
   const response=await route.fetch(); held=true;
   await gate; await route.fulfill({response});
  });
  await page.getByRole('button',{name:'Check now',exact:true}).click();
  await expect.poll(()=>held).toBe(true);
  fixture('crawl',id,'Changed evidence for concurrency regression.');
  await expect(page.getByText('A new version is ready to review.',{exact:true})).toBeVisible();
  release();
  await page.unrouteAll({behavior:'wait'});
  await expect(page.getByText('A new version is ready to review.',{exact:true})).toBeVisible();
 } finally {release();fixture('cleanup',id);}
});
