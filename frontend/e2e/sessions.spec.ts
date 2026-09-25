import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
function fixture(...args: string[]) {
  return execFileSync(resolve("../.venv/bin/python"), [resolve("../tests/ui_fixture.py"), ...args], {encoding: "utf8"});
}
test("visited sessions survive reload and cookie loss, deduplicate, and can be forgotten", async ({page, context}) => {
  const first = JSON.parse(fixture("seed"));
  const second = JSON.parse(fixture("seed"));
  try {
    await page.goto(`/s/${first.id}#key=${first.token}`);
    await expect(page).toHaveURL(`/s/${first.id}`);
    await expect(page.locator(".document-preview")).toContainText("Acme");
    await page.goto(`/s/${second.id}#key=${second.token}`);
    await expect(page).toHaveURL(`/s/${second.id}`);
    await expect(page.locator(".document-preview")).toContainText("Acme");
    await page.getByRole("link", {name: "Brief home"}).click();
    const list = page.getByRole("region", {name: "Your saved sessions"});
    await expect(list.getByRole("link")).toHaveCount(2);
    await expect(list.getByRole("link").first()).toHaveAttribute("href", `/s/${second.id}`);
    await context.clearCookies();
    await page.reload();
    await list.locator(`a[href="/s/${first.id}"]`).click();
    await expect(page.locator(".document-preview")).toContainText("Acme");
    await page.getByRole("link", {name: "Brief home"}).click();
    await expect(list.getByRole("link")).toHaveCount(2);
    await expect(list.getByRole("link").first()).toHaveAttribute("href", `/s/${first.id}`);
    await page.setViewportSize({width: 320, height: 900});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    expect((await new AxeBuilder({page}).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
    await list.getByRole("button", {name: /Remove saved session/}).first().click();
    await expect(list.getByRole("link")).toHaveCount(1);
    await page.reload();
    await expect(list.getByRole("link")).toHaveCount(1);
    await page.goto(`/s/${first.id}`);
    await expect(page.locator(".document-preview")).toContainText("Acme");
  } finally {
    fixture("cleanup", first.id); fixture("cleanup", second.id);
  }
});

test("cookie-only sessions are remembered and damaged storage does not block the home page", async ({page, context}) => {
  const {id, token} = JSON.parse(fixture("seed"));
  try {
    await page.goto(`/s/${id}#key=${token}`);
    await expect(page).toHaveURL(`/s/${id}`);
    await expect(page.locator(".document-preview")).toContainText("Acme");
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem("brief.sessions.v1") || "[]")[0]?.token)).toBe(token);
    await context.clearCookies();
    await page.goto("/");
    await page.getByRole("region", {name: "Your saved sessions"}).getByRole("link").click();
    await expect(page.locator(".document-preview")).toContainText("Acme");
    await page.evaluate(() => localStorage.setItem("brief.sessions.v1", "broken JSON"));
    await page.goto("/");
    await expect(page.getByRole("button", {name: "Create a brief"})).toBeVisible();
    await expect(page.getByRole("region", {name: "Your saved sessions"})).toHaveCount(0);
  } finally { fixture("cleanup", id); }
});
