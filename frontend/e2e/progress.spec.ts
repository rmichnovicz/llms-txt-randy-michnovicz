import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
function fixture(...args: string[]) {
  return execFileSync(resolve("../.venv/bin/python"), [resolve("../tests/ui_fixture.py"), ...args], { encoding: "utf8" });
}
test("live activity streams updates and resumes after reload", async ({ page }) => {
  const {id, token} = JSON.parse(fixture("seed"));
  try {
    await page.setViewportSize({width:320,height:800});
    await page.goto(`/s/${id}#key=${token}`);
    await page.getByRole("button", {name:"Check now",exact:true}).click();
    const activity = page.getByRole("region", {name:"Live activity"});
    await expect(activity).toBeVisible();
    fixture("progress", id);
    await expect(activity).toContainText("Read: Plans and pricing");
    await expect(activity).toContainText("7 readable pages · 19 links discovered");
    await page.reload();
    await expect(activity).toContainText("Read: Plans and pricing");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    fixture("crawl", id);
    await expect(activity).toHaveCount(0);
    await expect(page.getByText("A new version is ready to review.", {exact:true})).toBeVisible();
  } finally { fixture("cleanup", id); }
});
