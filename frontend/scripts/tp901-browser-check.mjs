import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright-core";

const baseUrl = process.env.TP901_BASE_URL ?? "http://127.0.0.1:8088";
const edgePath = process.env.TP901_EDGE_PATH;
const adminEmail = process.env.PODORIA_LOCAL_ADMIN_EMAIL;
const adminPassword = process.env.PODORIA_LOCAL_ADMIN_PASSWORD;

if (!edgePath || !adminEmail || !adminPassword) {
  throw new Error(
    "TP901_EDGE_PATH, PODORIA_LOCAL_ADMIN_EMAIL and PODORIA_LOCAL_ADMIN_PASSWORD are required.",
  );
}

const evidenceDir = path.resolve(process.cwd(), "../docs/evidence/tp-901");
await mkdir(evidenceDir, { recursive: true });
const axeSource = await readFile(path.resolve(process.cwd(), "node_modules/axe-core/axe.min.js"), "utf8");
const browser = await chromium.launch({ executablePath: edgePath, headless: true });

const routes = [
  { id: "overview", path: "/", heading: "Добрий день", screenshot: true },
  { id: "calendar", path: "/calendar", heading: "Розклад клініки", screenshot: true },
  { id: "patients", path: "/patients", heading: "Каталог пацієнтів", screenshot: true },
  { id: "work-items", path: "/work-items", heading: "Внутрішні справи" },
  { id: "finance", path: "/finance", heading: "Оплати та каса", screenshot: true },
  { id: "finance-shifts", path: "/finance/shifts", heading: "Історія касових змін" },
  { id: "inventory", path: "/inventory", heading: "Склад і матеріали", screenshot: true },
  { id: "notifications", path: "/notifications", heading: "Сповіщення" },
  { id: "audit", path: "/audit", heading: "Журнал дій" },
  { id: "analytics", path: "/analytics", heading: "Аналітика клініки", screenshot: true },
  { id: "team", path: "/team", heading: "Команда" },
  { id: "settings", path: "/settings", heading: "Налаштування кабінету" },
  { id: "password-resets", path: "/password-resets", heading: "Запити на відновлення доступу" },
];

const viewports = [
  { name: "desktop", viewport: { width: 1440, height: 900 }, mobile: false },
  { name: "tablet", viewport: { width: 1024, height: 768 }, mobile: false },
  { name: "mobile", viewport: { width: 390, height: 844 }, mobile: true },
];

const results = {
  generated_at: new Date().toISOString(),
  browser: "Microsoft Edge (Playwright chromium channel via explicit executable)",
  base_url: baseUrl,
  route_count: routes.length,
  viewports: [],
  keyboard: null,
  mobile_more: null,
};

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
  const session = await response.json();
  const requiredRouteIds = routes
    .map((route) => route.id)
    .filter((routeId) => routeId !== "finance-shifts");
  const missing = requiredRouteIds.filter((routeId) => !session.route_ids.includes(routeId));
  if (missing.length > 0) {
    throw new Error(`Admin session is missing route ids: ${missing.join(", ")}.`);
  }
}

async function waitForRoute(page, route) {
  await page.goto(`${baseUrl}${route.path}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: route.heading, exact: true }).waitFor();
  await page.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => undefined);
}

async function shellMetrics(page) {
  return page.locator("main#main-content").evaluate(() => {
    const sidebar = document.querySelector(".sidebar");
    const mobileNavigation = document.querySelector(".mobile-bottom-nav");
    if (!sidebar || !mobileNavigation) throw new Error("Responsive shell nodes are missing.");
    const touchSelectors = [
      ".mobile-bottom-nav a",
      ".mobile-bottom-nav button",
      "main .button",
      "main .icon-button",
      "main input",
      "main select",
      "main textarea",
    ].join(",");
    const undersizedTouchTargets = Array.from(document.querySelectorAll(touchSelectors))
      .filter((element) => {
        if (element.matches(".sr-only")) return false;
        const hitTarget = element.matches("input, select, textarea")
          ? (element.closest("label") ?? element)
          : element;
        const style = getComputedStyle(hitTarget);
        const rect = hitTarget.getBoundingClientRect();
        return style.display !== "none"
          && style.visibility !== "hidden"
          && rect.width > 0
          && rect.height > 0
          && (rect.width < 43.5 || rect.height < 43.5);
      })
      .map((element) => {
        const hitTarget = element.matches("input, select, textarea")
          ? (element.closest("label") ?? element)
          : element;
        const rect = hitTarget.getBoundingClientRect();
        return {
          label: element.getAttribute("aria-label") ?? hitTarget.textContent?.trim().slice(0, 80) ?? element.tagName,
          selector: hitTarget.className || hitTarget.tagName.toLowerCase(),
          width: Math.round(rect.width * 10) / 10,
          height: Math.round(rect.height * 10) / 10,
        };
      });
    return {
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      mainId: document.querySelector("main")?.id ?? null,
      sidebarDisplay: getComputedStyle(sidebar).display,
      mobileNavigationDisplay: getComputedStyle(mobileNavigation).display,
      undersizedTouchTargets,
    };
  });
}

async function axeViolations(page) {
  return page.evaluate(async () => {
    const scan = await globalThis.axe.run(document, {
      runOnly: {
        type: "tag",
        values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
      },
    });
    return scan.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      help: violation.help,
      nodes: violation.nodes.map((node) => ({
        target: node.target,
        failure_summary: node.failureSummary,
      })),
    }));
  });
}

function assertShell(name, metrics, mobile) {
  if (metrics.mainId !== "main-content") {
    throw new Error(`${name} is missing main#main-content.`);
  }
  if (metrics.scrollWidth > metrics.clientWidth) {
    throw new Error(`${name} page overflow: ${JSON.stringify(metrics)}.`);
  }
  if (mobile) {
    if (metrics.sidebarDisplay !== "none" || metrics.mobileNavigationDisplay === "none") {
      throw new Error(`${name} mobile shell is not active: ${JSON.stringify(metrics)}.`);
    }
    if (metrics.undersizedTouchTargets.length > 0) {
      throw new Error(`${name} has undersized primary touch targets: ${JSON.stringify(metrics.undersizedTouchTargets)}.`);
    }
  } else if (metrics.sidebarDisplay === "none" || metrics.mobileNavigationDisplay !== "none") {
    throw new Error(`${name} desktop/tablet shell is not active: ${JSON.stringify(metrics)}.`);
  }
}

function assertNoBrowserErrors(name, errors) {
  if (errors.length > 0) {
    throw new Error(`${name} browser errors: ${errors.map((entry) => entry.message).join(" | ")}.`);
  }
}

function assertNoSeriousAxeViolations(name, violations) {
  const blocking = violations.filter((violation) => ["serious", "critical"].includes(violation.impact));
  if (blocking.length > 0) {
    throw new Error(`${name} axe violations: ${JSON.stringify(blocking)}.`);
  }
}

async function runRouteMatrix(config) {
  const context = await browser.newContext({ viewport: config.viewport });
  await context.addInitScript({ content: axeSource });
  await loginViaApi(context);
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  let activeRoute = "bootstrap";
  let routeErrors = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      routeErrors.push({ route: activeRoute, message: `${message.type()}: ${message.text()}` });
    }
  });
  page.on("pageerror", (error) => {
    routeErrors.push({ route: activeRoute, message: `pageerror: ${error.message}` });
  });

  const viewportResult = { name: config.name, viewport: config.viewport, routes: [] };
  try {
    for (const route of routes) {
      activeRoute = route.id;
      routeErrors = [];
      await waitForRoute(page, route);
      const metrics = await shellMetrics(page);
      const violations = await axeViolations(page);
      assertShell(`${config.name} ${route.id}`, metrics, config.mobile);
      assertNoSeriousAxeViolations(`${config.name} ${route.id}`, violations);
      assertNoBrowserErrors(`${config.name} ${route.id}`, routeErrors);
      if (route.screenshot) {
        await page.screenshot({
          fullPage: true,
          path: path.join(evidenceDir, `${route.id}-${config.name}.png`),
        });
      }
      viewportResult.routes.push({
        id: route.id,
        path: route.path,
        heading: route.heading,
        metrics,
        axe_violations: violations,
        browser_errors: routeErrors,
      });
    }
  } finally {
    await context.close();
  }
  results.viewports.push(viewportResult);
}

async function runKeyboardJourney() {
  const context = await browser.newContext({ viewport: viewports[0].viewport });
  await loginViaApi(context);
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  try {
    await waitForRoute(page, routes[0]);
    await page.keyboard.press("Tab");
    const skipLinkText = await page.evaluate(() => document.activeElement?.textContent?.trim() ?? null);
    if (skipLinkText !== "До основного вмісту") {
      throw new Error(`First Tab focused ${JSON.stringify(skipLinkText)} instead of the skip link.`);
    }
    await page.keyboard.press("Enter");
    const skipDestination = await page.evaluate(() => ({
      hash: window.location.hash,
      activeId: document.activeElement?.id ?? null,
    }));
    if (skipDestination.hash !== "#main-content" || skipDestination.activeId !== "main-content") {
      throw new Error(`Skip link did not focus main: ${JSON.stringify(skipDestination)}.`);
    }

    const searchTrigger = page.getByRole("button", { name: "Відкрити глобальний пошук" });
    await searchTrigger.focus();
    await page.keyboard.press("Control+K");
    const searchDialog = page.getByRole("dialog", { name: "Глобальний пошук" });
    await searchDialog.waitFor();
    const searchOpenState = await page.evaluate(() => ({
      inputFocused: document.activeElement?.matches("#global-search-dialog input[type='search']") ?? false,
      bodyOverflow: document.body.style.overflow,
    }));
    if (!searchOpenState.inputFocused || searchOpenState.bodyOverflow !== "hidden") {
      throw new Error(`Global search focus/scroll lock failed: ${JSON.stringify(searchOpenState)}.`);
    }
    await page.keyboard.press("Escape");
    await searchDialog.waitFor({ state: "detached" });
    await page.waitForFunction(
      () => document.activeElement?.getAttribute("aria-label") === "Відкрити глобальний пошук",
      null,
      { timeout: 2_000 },
    );
    const searchCloseState = await page.evaluate(() => ({
      triggerFocused: document.activeElement?.getAttribute("aria-label") === "Відкрити глобальний пошук",
      bodyOverflow: document.body.style.overflow,
    }));
    if (!searchCloseState.triggerFocused || searchCloseState.bodyOverflow !== "") {
      throw new Error(`Global search focus restoration failed: ${JSON.stringify(searchCloseState)}.`);
    }

    const navigation = page.getByRole("navigation", { name: "Основна навігація" });
    const journey = [
      ["Календар", "Розклад клініки"],
      ["Пацієнти", "Каталог пацієнтів"],
      ["Фінанси", "Оплати та каса"],
      ["Склад", "Склад і матеріали"],
      ["Аналітика", "Аналітика клініки"],
      ["Журнал дій", "Журнал дій"],
    ];
    for (const [linkName, heading] of journey) {
      await navigation.getByRole("link", { name: linkName, exact: true }).click();
      await page.getByRole("heading", { name: heading, exact: true }).waitFor();
    }
    results.keyboard = { skipLinkText, skipDestination, searchOpenState, searchCloseState, journey };
  } finally {
    await context.close();
  }
}

async function runMobileMoreJourney() {
  const context = await browser.newContext({ viewport: viewports[2].viewport });
  await loginViaApi(context);
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  try {
    await waitForRoute(page, routes[0]);
    const moreTrigger = page.getByRole("button", { name: "Ще", exact: true });
    await moreTrigger.click();
    const dialog = page.getByRole("dialog", { name: /.+/ });
    await dialog.waitFor();
    const openState = await page.evaluate(() => ({
      activeLabel: document.activeElement?.getAttribute("aria-label"),
      bodyOverflow: document.body.style.overflow,
    }));
    if (openState.activeLabel !== "Закрити додаткове меню" || openState.bodyOverflow !== "hidden") {
      throw new Error(`Mobile More focus/scroll lock failed: ${JSON.stringify(openState)}.`);
    }
    await dialog.getByRole("link", { name: "Аналітика", exact: true }).click();
    await page.getByRole("heading", { name: "Аналітика клініки", exact: true }).waitFor();
    if (await dialog.count() !== 0) throw new Error("Mobile More dialog remained open after navigation.");

    await moreTrigger.click();
    await dialog.waitFor();
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "detached" });
    await page.waitForFunction(
      () => document.activeElement?.textContent?.trim() === "Ще",
      null,
      { timeout: 2_000 },
    );
    const closeState = await page.evaluate(() => ({
      triggerFocused: document.activeElement?.textContent?.trim() === "Ще",
      bodyOverflow: document.body.style.overflow,
    }));
    if (!closeState.triggerFocused || closeState.bodyOverflow !== "") {
      throw new Error(`Mobile More close restoration failed: ${JSON.stringify(closeState)}.`);
    }
    results.mobile_more = { openState, closeState, navigated_to: "/analytics" };
  } finally {
    await context.close();
  }
}

try {
  for (const config of viewports) {
    await runRouteMatrix(config);
  }
  await runKeyboardJourney();
  await runMobileMoreJourney();
  await writeFile(
    path.join(evidenceDir, "browser-gate.json"),
    `${JSON.stringify(results, null, 2)}\n`,
    "utf8",
  );
  console.log("TP-901 cross-feature Edge, axe, responsive and keyboard gate passed.");
} catch (error) {
  results.failure = error instanceof Error ? error.message : String(error);
  await writeFile(
    path.join(evidenceDir, "browser-gate.json"),
    `${JSON.stringify(results, null, 2)}\n`,
    "utf8",
  );
  throw error;
} finally {
  await Promise.race([
    browser.close(),
    new Promise((resolve) => setTimeout(resolve, 3_000)),
  ]);
  setTimeout(() => process.exit(process.exitCode ?? 0), 500);
}
