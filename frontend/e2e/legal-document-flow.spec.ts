import { expect, test } from "@playwright/test";

const apiBaseURL = (process.env.E2E_API_URL || process.env.API_URL || "http://127.0.0.1:5000").replace(/\/$/, "");
const adminEmail = process.env.E2E_ADMIN_EMAIL || process.env.BOOTSTRAP_ADMIN_EMAIL || "";
const adminPassword = process.env.E2E_ADMIN_PASSWORD || process.env.BOOTSTRAP_ADMIN_PASSWORD || "";

async function expectOk(response: { ok(): boolean; status(): number; url(): string; text(): Promise<string> }) {
  if (!response.ok()) {
    throw new Error(`${response.status()} ${response.url()}: ${await response.text()}`);
  }
}

async function signIn(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Password").fill(adminPassword);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

test.describe("LegalDocuMan browser smoke", () => {
  test("redirects protected upload route to login", async ({ page }) => {
    await page.goto("/upload");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();
  });

  test("login, upload text file, open detail, and download through the API", async ({ page }) => {
    test.skip(!adminEmail || !adminPassword, "Set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD to run authenticated e2e flow.");

    await signIn(page);

    await page.goto("/upload");
    await expect(page.getByRole("heading", { name: /upload documents/i })).toBeVisible();

    const uploadResponsePromise = page.waitForResponse((response) =>
      response.url().includes("/api/v1/upload") && response.request().method() === "POST"
    );

    await page.locator('input[type="file"]').setInputFiles({
      name: "playwright-smoke-contract.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Playwright smoke contract. Effective January 1, 2026. Signed by Acme Corp."),
    });

    const uploadResponse = await uploadResponsePromise;
    await expectOk(uploadResponse);
    const upload = (await uploadResponse.json()) as { id: number; job_id: number; job_status: string };
    expect(upload.id).toBeGreaterThan(0);
    expect(upload.job_id).toBeGreaterThan(0);

    await expect(page.getByText(/Upload Results/i)).toBeVisible();
    await expect(page.getByRole("link", { name: "View" }).first()).toBeVisible();

    const token = await page.evaluate(() => window.localStorage.getItem("legaldocuman_token"));
    expect(token).toBeTruthy();
    const authHeaders = { Authorization: `Bearer ${token}` };

    await expect
      .poll(
        async () => {
          const response = await page.request.get(`${apiBaseURL}/api/v1/jobs/${upload.job_id}`, { headers: authHeaders });
          await expectOk(response);
          const job = (await response.json()) as { document_id: number };
          return job.document_id;
        },
        { timeout: 45_000, intervals: [1_000, 2_000, 3_000] }
      )
      .toBe(upload.id);

    const jobResponse = await page.request.get(`${apiBaseURL}/api/v1/jobs/${upload.job_id}`, { headers: authHeaders });
    await expectOk(jobResponse);
    const job = (await jobResponse.json()) as { status: string; document_id: number };

    await page.goto(`/documents/${upload.id}`);
    await expect(page.getByRole("heading", { name: /document details/i })).toBeVisible();
    await expect(page.getByText("playwright-smoke-contract.txt")).toBeVisible();

    const detailResponse = await page.request.get(`${apiBaseURL}/api/v1/documents/${upload.id}`, { headers: authHeaders });
    await expectOk(detailResponse);
    const detail = (await detailResponse.json()) as { id: number; status: string; original_name: string };
    expect(detail).toMatchObject({ id: upload.id, original_name: "playwright-smoke-contract.txt" });

    if (detail.status === "completed") {
      await expect(page.getByRole("button", { name: /download/i })).toBeVisible();
    }

    const tokenResponse = await page.request.post(`${apiBaseURL}/api/v1/documents/${upload.id}/download-token`, {
      headers: authHeaders,
    });
    await expectOk(tokenResponse);
    const downloadToken = (await tokenResponse.json()) as { download_token: string };
    expect(downloadToken.download_token).toBeTruthy();

    const downloadResponse = await page.request.get(
      `${apiBaseURL}/api/v1/documents/${upload.id}/download?download_token=${encodeURIComponent(downloadToken.download_token)}`
    );
    await expectOk(downloadResponse);
    expect((await downloadResponse.body()).byteLength).toBeGreaterThan(0);

    expect(["pending", "queued", "processing", "completed", "failed"]).toContain(job.status);
  });
});
