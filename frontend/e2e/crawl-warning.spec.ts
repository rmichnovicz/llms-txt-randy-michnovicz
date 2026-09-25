import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

test("failed crawl shows its redirect and offers a prefilled new brief", async ({
  page,
}) => {
  const root = resolve("..");
  const fixture = (...args: string[]) =>
    execFileSync(
      resolve(root, ".venv/bin/python"),
      [resolve(root, "tests/ui_fixture.py"), ...args],
      { cwd: root },
    );
  let id = "";
  try {
    await page.goto("/");
    await page.getByLabel("Website URL").fill("acme.example.com");
    await page.getByRole("button", { name: "Create a brief" }).click();
    await expect(page).toHaveURL(/\/s\/[a-f0-9-]+$/);
    id = new URL(page.url()).pathname.split("/").pop()!;
    fixture("fail", id);
    await page.route(`**/api/projects/${id}/document*`, async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.jobs[0].result = {
        warnings: [
          {
            url: "https://acme.example.com/",
            reason: "This page redirects outside the allowed crawl scope.",
            redirect_url: "https://docs.example.com/latest/",
          },
        ],
      };
      await route.fulfill({ response, json: body });
    });
    await page.reload();
    await expect(page.getByRole("alert")).toContainText(
      "https://docs.example.com/latest/",
    );
    await page
      .getByRole("link", { name: "Start a brief at this address" })
      .click();
    await expect(page.getByLabel("Website URL")).toHaveValue(
      "https://docs.example.com/latest/",
    );
  } finally {
    if (id) fixture("cleanup", id);
  }
});
