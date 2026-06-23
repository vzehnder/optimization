import { expect, test } from "@playwright/test";

test("FastAPI serves an authenticated React shell that survives direct refresh", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("ada@example.local");
  await page.getByLabel("Password").fill("smoke-test-password");
  await page.getByRole("button", { name: "Sign In" }).click();

  await page.goto("/react");
  await expect(page.getByText("Ada Analyst")).toBeVisible();
  await expect(page.getByText("analyst", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Sistema" }).click();
  await expect(page).toHaveURL(/\/react\/system$/);
  await expect(
    page.getByRole("heading", { name: "Estado del sistema" }),
  ).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Estado del sistema" }),
  ).toBeVisible();
  await expect(page.getByText("Ada Analyst")).toBeVisible();
});
