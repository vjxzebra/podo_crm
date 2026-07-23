import { mkdir } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright-core";

const baseUrl = process.env.TP206_BASE_URL ?? "http://127.0.0.1:8088";
const edgePath = process.env.TP206_EDGE_PATH;
const adminEmail = process.env.TP206_ADMIN_EMAIL;
const adminPassword = process.env.TP206_ADMIN_PASSWORD;

if (!edgePath || !adminEmail || !adminPassword) {
  throw new Error("TP206_EDGE_PATH and local admin credentials are required.");
}

const evidenceDir = path.resolve(process.cwd(), "../docs/evidence/tp-206");
await mkdir(evidenceDir, { recursive: true });
const browser = await chromium.launch({ executablePath: edgePath, headless: true });

async function csrfToken(context) {
  await context.request.get(`${baseUrl}/api/v1/session`);
  const cookies = await context.cookies(baseUrl);
  const csrfCookie = cookies.find((cookie) => cookie.name === "podoria_csrftoken");
  if (!csrfCookie) throw new Error("CSRF bootstrap cookie is missing.");
  return csrfCookie.value;
}

async function loginViaApi(context) {
  const response = await context.request.post(`${baseUrl}/api/v1/auth/login`, {
    data: { email: adminEmail, password: adminPassword },
    headers: { "X-CSRFToken": await csrfToken(context) },
  });
  if (response.status() !== 200) {
    throw new Error(`Login API returned ${response.status()}: ${await response.text()}`);
  }
  const session = await response.json();
  if (!session.route_ids.includes("settings")) throw new Error("Admin settings route is missing.");
}

async function assertHealthyPage(page, errors) {
  const fatal = errors.filter((message) => !message.includes("favicon"));
  if (fatal.length) throw new Error(`Browser console errors: ${fatal.join(" | ")}`);
  const overflow = await page.locator("body").evaluate((body) => ({
    scrollWidth: body.scrollWidth,
    viewportWidth: window.innerWidth,
  }));
  if (overflow.scrollWidth > overflow.viewportWidth) {
    throw new Error(`Page has horizontal overflow: ${JSON.stringify(overflow)}`);
  }
}

async function settingsPage(viewport) {
  const context = await browser.newContext({ viewport });
  await loginViaApi(context);
  const page = await context.newPage();
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.setDefaultTimeout(12_000);
  await page.goto(`${baseUrl}/settings`);
  await page.getByRole("heading", { name: "Налаштування кабінету" }).waitFor();
  return { context, errors, page };
}

let failure = null;

try {
  const desktop = await settingsPage({ width: 1440, height: 900 });
  await desktop.page.getByTestId("settings-statuses-tab").click();
  await desktop.page.getByRole("heading", { name: "Системні статуси" }).waitFor();
  await desktop.page.getByText("NEW", { exact: true }).waitFor();
  const statusCodes = await desktop.page.locator(".status-card code").allTextContents();
  const expectedCodes = [
    "NEW",
    "PENDING_CONFIRMATION",
    "CONFIRMED",
    "ARRIVED",
    "IN_PROGRESS",
    "COMPLETED",
    "CANCELED",
    "NO_SHOW",
  ];
  if (JSON.stringify(statusCodes) !== JSON.stringify(expectedCodes)) {
    throw new Error(`Unexpected system status registry: ${JSON.stringify(statusCodes)}`);
  }
  if ((await desktop.page.getByRole("button", { name: /^Налаштувати / }).count()) !== 8) {
    throw new Error("Expected eight status edit controls.");
  }
  await assertHealthyPage(desktop.page, desktop.errors);
  await desktop.page.screenshot({
    path: path.join(evidenceDir, "status-configs-1440x900.png"),
  });
  await desktop.page.getByTestId("settings-schedule-tab").click();
  await desktop.page.getByRole("heading", { name: "Робочий час клініки" }).waitFor();
  await desktop.page.getByLabel("Понеділок початок", { exact: true }).waitFor();
  if ((await desktop.page.locator(".schedule-day").count()) !== 7) {
    throw new Error("Expected seven clinic workdays.");
  }
  if ((await desktop.page.locator(".schedule-break").count()) !== 5) {
    throw new Error("Expected five seeded weekday breaks.");
  }
  await desktop.page.screenshot({
    path: path.join(evidenceDir, "clinic-schedule-1440x900.png"),
  });
  await desktop.context.close();
  console.log("status-and-schedule-desktop: ok");

  const tablet = await settingsPage({ width: 768, height: 1024 });
  await tablet.page.getByTestId("settings-statuses-tab").click();
  await tablet.page.getByRole("heading", { name: "Системні статуси" }).waitFor();
  await tablet.page.getByText("ARRIVED", { exact: true }).waitFor();
  await tablet.page.getByRole("button", { name: "Налаштувати Пацієнт прийшов" }).click();
  const dialog = tablet.page.getByRole("dialog", { name: "Налаштувати статус" });
  await dialog.waitFor();
  if ((await dialog.getByRole("checkbox").count()) !== 3) {
    throw new Error("Expected three manual-role controls.");
  }
  if ((await dialog.getByLabel("Код статусу").count()) !== 0) {
    throw new Error("Immutable system code unexpectedly became editable.");
  }
  await dialog.getByLabel("Зрозуміла назва").fill("Пацієнт у клініці");
  await dialog.getByText("Є незбережені зміни.").waitFor();
  await assertHealthyPage(tablet.page, tablet.errors);
  await tablet.page.screenshot({
    path: path.join(evidenceDir, "status-editor-unsaved-768x1024.png"),
  });
  await tablet.context.close();
  console.log("status-editor-tablet: ok");

  const mobile = await settingsPage({ width: 390, height: 844 });
  await mobile.page.getByTestId("settings-schedule-tab").click();
  await mobile.page.getByRole("heading", { name: "Робочий час клініки" }).waitFor();
  await mobile.page.getByLabel("Понеділок початок", { exact: true }).waitFor();
  const layout = await mobile.page.locator(".schedule-days").evaluate((grid) => {
    const day = grid.querySelector(".schedule-day");
    const rect = day?.getBoundingClientRect();
    return {
      columns: getComputedStyle(grid).gridTemplateColumns.split(" ").length,
      dayLeft: rect?.left ?? -1,
      dayRight: rect?.right ?? Number.POSITIVE_INFINITY,
      viewportWidth: window.innerWidth,
    };
  });
  if (layout.columns !== 1 || layout.dayLeft < 0 || layout.dayRight > layout.viewportWidth) {
    throw new Error(`Mobile schedule grid is clipped: ${JSON.stringify(layout)}`);
  }
  await assertHealthyPage(mobile.page, mobile.errors);
  await mobile.page.screenshot({
    path: path.join(evidenceDir, "clinic-schedule-390x844.png"),
  });
  await mobile.context.close();
  console.log("schedule-mobile: ok");

  console.log(JSON.stringify({
    desktopStatuses: "ok",
    desktopSchedule: "ok",
    tabletStatusEditor: "ok",
    mobileSchedule: "ok",
  }));
} catch (error) {
  failure = error;
  console.error(error);
} finally {
  await Promise.race([browser.close(), new Promise((resolve) => setTimeout(resolve, 3_000))]);
  process.exit(failure === null ? 0 : 1);
}
