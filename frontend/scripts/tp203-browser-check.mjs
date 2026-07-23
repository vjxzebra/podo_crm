import { mkdir } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright-core";

const baseUrl = process.env.TP203_BASE_URL ?? "http://127.0.0.1:8088";
const edgePath = process.env.TP203_EDGE_PATH;
const adminPassword = process.env.TP203_ADMIN_PASSWORD;
const receptionPassword = process.env.TP203_RECEPTION_PASSWORD;

if (!edgePath || !adminPassword || !receptionPassword) {
  throw new Error("TP203_EDGE_PATH and local test passwords are required.");
}

const evidenceDir = path.resolve(process.cwd(), "../docs/evidence/tp-203");
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
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const desktopPage = await desktop.newPage();
  desktopPage.setDefaultTimeout(12_000);
  const adminSession = await loginViaApi(
    desktop,
    "tp203-admin@podoria.local",
    adminPassword,
  );
  if (!adminSession.route_ids.includes("team")) {
    throw new Error("Admin session does not expose the team route.");
  }
  await desktopPage.goto(`${baseUrl}/team`);
  await desktopPage.getByRole("heading", { name: "Команда" }).waitFor();
  await desktopPage.locator(".team-table tbody tr").first().waitFor();
  if ((await desktopPage.locator(".team-table tbody tr").count()) < 4) {
    throw new Error("Expected the admin and three TP-203 employee fixtures.");
  }
  await desktopPage.screenshot({
    path: path.join(evidenceDir, "team-list-1440x900.png"),
  });
  await desktop.close();
  console.log("admin-team-list: ok");

  const tablet = await browser.newContext({ viewport: { width: 768, height: 1024 } });
  const tabletPage = await tablet.newPage();
  tabletPage.setDefaultTimeout(12_000);
  await loginViaApi(tablet, "tp203-admin@podoria.local", adminPassword);
  await tabletPage.goto(`${baseUrl}/team`);
  await tabletPage.getByRole("heading", { name: "Команда" }).waitFor();
  await tabletPage.getByRole("button", { name: "Додати працівника" }).click();
  const createDialog = tabletPage.getByRole("dialog", { name: "Новий працівник" });
  await createDialog.waitFor();
  const roleSelect = createDialog.locator("select");
  if ((await roleSelect.count()) !== 1) {
    throw new Error("Expected one role selector in the create dialog.");
  }
  await roleSelect.selectOption("reception");
  await tabletPage.getByText("Спільний календар, пацієнти, справи", { exact: false }).waitFor();
  await tabletPage.screenshot({
    path: path.join(evidenceDir, "team-create-role-access-768x1024.png"),
  });
  await tablet.close();
  console.log("team-create-role-access: ok");

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const mobilePage = await mobile.newPage();
  mobilePage.setDefaultTimeout(12_000);
  await loginViaApi(mobile, "tp203-admin@podoria.local", adminPassword);
  await mobilePage.goto(`${baseUrl}/team`);
  await mobilePage.getByRole("heading", { name: "Команда" }).waitFor();
  await mobilePage.locator(".team-table tr").first().waitFor();
  await mobilePage.screenshot({
    path: path.join(evidenceDir, "team-cards-390x844.png"),
  });
  await mobile.close();
  console.log("mobile-team-cards: ok");

  const reception = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const receptionPage = await reception.newPage();
  receptionPage.setDefaultTimeout(12_000);
  const receptionSession = await loginViaApi(
    reception,
    "tp203-reception@podoria.local",
    receptionPassword,
  );
  if (receptionSession.route_ids.includes("team")) {
    throw new Error("Reception session unexpectedly exposes the team route.");
  }
  await receptionPage.goto(`${baseUrl}/team`);
  await receptionPage.getByRole("heading", { name: "Добрий день" }).waitFor();
  await receptionPage.getByRole("status").filter({ hasText: "Цей розділ недоступний" }).waitFor();
  if (await receptionPage.getByRole("link", { name: "Команда" }).count()) {
    throw new Error("Reception navigation exposes the team route.");
  }
  await reception.close();
  console.log("reception-team-boundary: ok");

  console.log(JSON.stringify({
    adminTeamList: "ok",
    createRoleAccess: "ok",
    mobileCards: "ok",
    receptionBoundary: "ok",
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
