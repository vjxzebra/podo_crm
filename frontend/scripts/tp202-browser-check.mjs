import { mkdir } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright-core";

const baseUrl = process.env.TP202_BASE_URL ?? "http://127.0.0.1:8088";
const edgePath = process.env.TP202_EDGE_PATH;
const adminPassword = process.env.TP202_ADMIN_PASSWORD;
const temporaryPassword = process.env.TP202_TEMPORARY_PASSWORD;

if (!edgePath || !adminPassword || !temporaryPassword) {
  throw new Error("TP202_EDGE_PATH and local test passwords are required.");
}

const evidenceDir = path.resolve(process.cwd(), "../docs/evidence/tp-202");
await mkdir(evidenceDir, { recursive: true });

const browser = await chromium.launch({ executablePath: edgePath, headless: true });

async function csrfToken(context) {
  await context.request.get(`${baseUrl}/api/v1/session`);
  const cookies = await context.cookies(baseUrl);
  const csrfCookie = cookies.find((cookie) => cookie.name === "podoria_csrftoken");
  if (!csrfCookie) {
    throw new Error("CSRF bootstrap cookie is missing.");
  }
  return csrfCookie.value;
}

async function loginViaApi(context, email, password) {
  const response = await context.request.post(`${baseUrl}/api/v1/auth/login`, {
    data: { email, password },
    headers: { "X-CSRFToken": await csrfToken(context) },
  });
  if (response.status() !== 200) {
    throw new Error(`Login API returned ${response.status()}: ${await response.text()}`);
  }
  return response.json();
}

let failure = null;

try {
  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const mobilePage = await mobile.newPage();
  mobilePage.setDefaultTimeout(12_000);
  await mobilePage.goto(`${baseUrl}/login`);
  await mobilePage.getByRole("heading", { name: "Вхід до кабінету" }).waitFor();
  await mobilePage.getByRole("button", { name: "Забули пароль?" }).click();
  await mobilePage.getByRole("dialog", { name: "Забули пароль?" }).waitFor();
  await mobilePage.getByRole("textbox", { name: "Робочий email" }).fill("unknown.tp202@podoria.local");
  await mobilePage.getByRole("button", { name: "Створити запит" }).click();
  await mobilePage.getByRole("heading", { name: "Запит прийнято" }).waitFor();
  await mobilePage.screenshot({
    path: path.join(evidenceDir, "forgot-generic-success-390x844.png"),
  });
  await mobile.close();
  console.log("forgot-generic: ok");

  const forced = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const forcedPage = await forced.newPage();
  forcedPage.setDefaultTimeout(12_000);
  const forcedSession = await loginViaApi(
    forced,
    "olena.tp202@podoria.local",
    temporaryPassword,
  );
  if (!forcedSession.must_change_password || forcedSession.route_ids.length !== 0) {
    throw new Error("Forced session unexpectedly exposes workspace routes.");
  }
  await forcedPage.goto(`${baseUrl}/patients`);
  await forcedPage.getByRole("heading", { name: "Створіть власний пароль" }).waitFor();
  if (await forcedPage.getByTestId("desktop-sidebar").count()) {
    throw new Error("First-login gate exposes the application shell.");
  }
  await forcedPage.screenshot({
    path: path.join(evidenceDir, "first-login-block-1440x900.png"),
  });
  await forced.close();
  console.log("first-login-block: ok");

  const admin = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const adminPage = await admin.newPage();
  adminPage.setDefaultTimeout(12_000);
  await loginViaApi(admin, "admin.tp202@podoria.local", adminPassword);
  const resetResponse = await admin.request.post(`${baseUrl}/api/v1/password-reset-requests`, {
    data: { email: "olena.tp202@podoria.local" },
    headers: { "X-CSRFToken": await csrfToken(admin) },
  });
  if (resetResponse.status() !== 202) {
    throw new Error(`Reset request API returned ${resetResponse.status()}.`);
  }
  await adminPage.goto(`${baseUrl}/password-resets`);
  await adminPage.getByRole("heading", { name: "Запити на відновлення доступу" }).waitFor();
  const employeeRequest = adminPage.locator(".reset-request-row");
  await adminPage.waitForTimeout(1_000);
  if ((await employeeRequest.count()) !== 1) {
    await adminPage.screenshot({
      path: path.join(evidenceDir, "admin-reset-queue-error-1440x900.png"),
    });
    throw new Error("Expected one pending reset request for the test employee.");
  }
  await employeeRequest.click();
  await adminPage.getByRole("button", { name: "Встановити пароль" }).waitFor();
  await adminPage.screenshot({
    path: path.join(evidenceDir, "admin-reset-queue-1440x900.png"),
  });
  await admin.close();
  console.log("admin-reset-queue: ok");

  const tablet = await browser.newContext({ viewport: { width: 768, height: 1024 } });
  const tabletPage = await tablet.newPage();
  tabletPage.setDefaultTimeout(12_000);
  await loginViaApi(tablet, "admin.tp202@podoria.local", adminPassword);
  await tabletPage.goto(baseUrl);
  await tabletPage.getByRole("heading", { name: "Добрий день" }).waitFor();
  const profileButton = tabletPage.locator(".profile-mini");
  if ((await profileButton.count()) !== 1) {
    throw new Error("Expected one tablet profile button.");
  }
  await profileButton.click();
  await tabletPage.getByRole("menuitem", { name: "Змінити пароль" }).click();
  await tabletPage.getByRole("dialog", { name: "Змінити пароль" }).waitFor();
  await tabletPage.screenshot({
    path: path.join(evidenceDir, "own-password-form-768x1024.png"),
  });
  await tablet.close();
  console.log("own-password-form: ok");

  console.log(JSON.stringify({
    forgotGeneric: "ok",
    firstLoginBlock: "ok",
    adminResetQueue: "ok",
    ownPasswordForm: "ok",
  }));
} catch (error) {
  failure = error;
  console.error(error);
} finally {
  await Promise.race([
    browser.close(),
    new Promise((resolve) => setTimeout(resolve, 3_000)),
  ]);
  process.exit(failure === null ? 0 : 1);
}
