import { mkdir } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright-core";

const baseUrl = process.env.TP701_BASE_URL ?? "http://127.0.0.1:8088";
const edgePath = process.env.TP701_EDGE_PATH;
const adminEmail = process.env.PODORIA_LOCAL_ADMIN_EMAIL;
const adminPassword = process.env.PODORIA_LOCAL_ADMIN_PASSWORD;
const expectShift = process.env.TP701_EXPECT_SHIFT === "1";

if (!edgePath || !adminEmail || !adminPassword) {
  throw new Error(
    "TP701_EDGE_PATH, PODORIA_LOCAL_ADMIN_EMAIL and PODORIA_LOCAL_ADMIN_PASSWORD are required.",
  );
}

const evidenceDir = path.resolve(process.cwd(), "../docs/evidence/tp-701");
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
    throw new Error(`Login API returned ${response.status()}.`);
  }
}

function columnCount(value) {
  return value === "none" ? 0 : value.trim().split(/\s+/).length;
}

async function openFinance(viewport) {
  const context = await browser.newContext({ viewport });
  await loginViaApi(context);
  const page = await context.newPage();
  const errors = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  page.setDefaultTimeout(12_000);
  await page.goto(`${baseUrl}/finance`);
  await page.getByRole("heading", { name: "Каса та поточна зміна" }).waitFor();
  return { context, errors, page };
}

async function populatedMetrics(page) {
  return page.locator(".finance-ledger").evaluate(() => {
    const summary = document.querySelector(".finance-summary-grid");
    const methods = document.querySelector(".finance-methods__grid");
    const row = document.querySelector(".finance-ledger-row");
    const head = document.querySelector(".finance-ledger-head");
    const hero = document.querySelector(".finance-shift-hero");
    const ledger = document.querySelector(".finance-ledger");
    const bounds = (element) => {
      const rect = element.getBoundingClientRect();
      return { left: rect.left, right: rect.right, width: rect.width };
    };
    return {
      clientWidth: document.documentElement.clientWidth,
      heroDirection: getComputedStyle(hero).flexDirection,
      ledger: bounds(ledger),
      ledgerHeaderDisplay: getComputedStyle(head).display,
      ledgerRow: bounds(row),
      ledgerRowColumns: getComputedStyle(row).gridTemplateColumns,
      mainButtons: document.querySelectorAll("main button").length,
      methodsColumns: getComputedStyle(methods).gridTemplateColumns,
      operationRows: document.querySelectorAll(".finance-ledger-row").length,
      scrollWidth: document.documentElement.scrollWidth,
      summaryColumns: getComputedStyle(summary).gridTemplateColumns,
    };
  });
}

function assertPopulatedMetrics(name, metrics, expectedColumns) {
  if (metrics.scrollWidth !== metrics.clientWidth) {
    throw new Error(`${name} page overflow: ${JSON.stringify(metrics)}`);
  }
  if (
    metrics.operationRows !== 8
    || metrics.mainButtons !== 0
    || columnCount(metrics.summaryColumns) !== expectedColumns.summary
    || columnCount(metrics.methodsColumns) !== expectedColumns.methods
    || columnCount(metrics.ledgerRowColumns) !== expectedColumns.ledger
    || metrics.ledgerHeaderDisplay !== expectedColumns.header
    || metrics.heroDirection !== expectedColumns.hero
    || metrics.ledger.right > metrics.clientWidth + 0.5
    || metrics.ledgerRow.right > metrics.clientWidth + 0.5
  ) {
    throw new Error(`${name} responsive contract failed: ${JSON.stringify(metrics)}`);
  }
}

async function assertNoErrors(name, errors) {
  if (errors.length > 0) throw new Error(`${name} browser errors: ${errors.join(" | ")}`);
}

async function runPopulated(name, viewport, screenshotName, expectedColumns) {
  const result = await openFinance(viewport);
  const page = result.page;
  await page.getByRole("region", { name: "Поточна касова зміна" }).waitFor();
  await page.getByRole("table", { name: "Касові операції поточної зміни" }).waitFor();
  const exactText = [
    "CSH-701000000000",
    "4 400,00 грн",
    "1 150,00 грн",
    "5 000,00 грн",
    "600,00 грн",
  ];
  for (const value of exactText) {
    if (await page.getByText(value, { exact: true }).count() !== 1) {
      throw new Error(`${name} expected one exact value: ${value}`);
    }
  }
  if (await page.getByRole("cell", { name: "Спосіб: Не застосовується" }).count() !== 2) {
    throw new Error(`${name} null payment method fallback is incorrect.`);
  }
  const metrics = await populatedMetrics(page);
  assertPopulatedMetrics(name, metrics, expectedColumns);
  await page.screenshot({ path: path.join(evidenceDir, screenshotName) });
  await assertNoErrors(name, result.errors);
  console.log(`${name}: ${JSON.stringify(metrics)}`);
  await result.context.close();
}

async function runNoShift() {
  const result = await openFinance({ width: 1440, height: 900 });
  const page = result.page;
  const trigger = page.getByRole("button", { name: "Відкрити касову зміну" });
  if (await trigger.count() !== 1) throw new Error("Expected exactly one open-shift CTA.");
  await page.getByRole("heading", { name: "Касову зміну ще не відкрито" }).waitFor();
  const pageWidths = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  if (pageWidths.clientWidth !== pageWidths.scrollWidth) {
    throw new Error(`No-shift page overflow: ${JSON.stringify(pageWidths)}`);
  }
  await page.screenshot({ path: path.join(evidenceDir, "no-shift-desktop-1440x900.png") });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Відкрити касову зміну?" });
  await dialog.waitFor();
  if (await dialog.locator("input").count() !== 0) {
    throw new Error("Opening balance dialog must not contain an input.");
  }
  if (await dialog.getByText("0,00 грн", { exact: true }).count() !== 1) {
    throw new Error("Opening balance must be fixed at zero.");
  }
  const dialogState = await dialog.evaluate((element) => ({
    activeLabel: document.activeElement?.textContent?.trim() ?? null,
    bodyOverflow: getComputedStyle(document.body).overflow,
    height: element.getBoundingClientRect().height,
    width: element.getBoundingClientRect().width,
  }));
  await page.screenshot({ path: path.join(evidenceDir, "open-shift-dialog-desktop-1440x900.png") });
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "detached" });
  const focusReturned = await trigger.evaluate((element) => document.activeElement === element);
  if (!focusReturned) throw new Error("Dialog focus did not return to the open-shift CTA.");
  await assertNoErrors("no-shift", result.errors);
  console.log(`no-shift: ${JSON.stringify({ ...pageWidths, dialogState, focusReturned })}`);
  await result.context.close();
}

let failure = null;
try {
  if (expectShift) {
    await runPopulated(
      "desktop",
      { width: 1440, height: 900 },
      "open-shift-desktop-1440x900.png",
      { header: "grid", hero: "row", ledger: 5, methods: 4, summary: 4 },
    );
    await runPopulated(
      "tablet",
      { width: 768, height: 1024 },
      "open-shift-tablet-768x1024.png",
      { header: "none", hero: "column", ledger: 2, methods: 2, summary: 2 },
    );
    await runPopulated(
      "mobile",
      { width: 390, height: 844 },
      "open-shift-mobile-390x844.png",
      { header: "none", hero: "column", ledger: 1, methods: 1, summary: 1 },
    );
  } else {
    await runNoShift();
  }
} catch (error) {
  failure = error;
} finally {
  await browser.close();
}

if (failure) throw failure;
