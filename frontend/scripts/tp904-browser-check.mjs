import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright-core";

const baseUrl = process.env.TP904_BASE_URL ?? "http://127.0.0.1:8088";
const edgePath = process.env.TP904_EDGE_PATH;
const requestedRole = process.env.TP904_ROLE;
const credentials = {
  admin: {
    email: process.env.PODORIA_LOCAL_ADMIN_EMAIL,
    password: process.env.PODORIA_LOCAL_ADMIN_PASSWORD,
  },
  reception: {
    email: process.env.PODORIA_LOCAL_RECEPTION_EMAIL,
    password: process.env.PODORIA_LOCAL_RECEPTION_PASSWORD,
  },
  podologist: {
    email: process.env.PODORIA_LOCAL_PODOLOGIST_EMAIL,
    password: process.env.PODORIA_LOCAL_PODOLOGIST_PASSWORD,
  },
};

if (
  !edgePath
  || Object.values(credentials).some(({ email, password }) => !email || !password)
) {
  throw new Error("TP904 Edge path and all three local role credentials are required.");
}

const evidenceDir = path.resolve(process.cwd(), "../docs/evidence/tp-904");
await mkdir(evidenceDir, { recursive: true });
const axeSource = await readFile(
  path.resolve(process.cwd(), "node_modules/axe-core/axe.min.js"),
  "utf8",
);
const browser = await chromium.launch({ executablePath: edgePath, headless: true });

const routeCatalog = {
  overview: { path: "/", heading: "Добрий день" },
  calendar: { path: "/calendar", heading: "Розклад клініки" },
  patients: { path: "/patients", heading: "Каталог пацієнтів" },
  "work-items": { path: "/work-items", heading: "Внутрішні справи" },
  finance: { path: "/finance", heading: "Оплати та каса" },
  "finance-shifts": { path: "/finance/shifts", heading: "Історія касових змін" },
  inventory: { path: "/inventory", heading: "Склад і матеріали" },
  analytics: { path: "/analytics", heading: "Аналітика клініки" },
  notifications: { path: "/notifications", heading: "Сповіщення" },
  team: { path: "/team", heading: "Команда" },
  audit: { path: "/audit", heading: "Журнал дій" },
  settings: { path: "/settings", heading: "Налаштування кабінету" },
  "password-resets": { path: "/password-resets", heading: "Запити на відновлення доступу" },
};

const roles = {
  podologist: {
    routeIds: ["overview", "calendar", "patients", "work-items", "notifications"],
    serverRouteIds: ["overview", "calendar", "patients", "work-items", "notifications"],
    forbiddenPaths: ["/finance", "/inventory", "/analytics", "/team", "/audit", "/settings"],
  },
  reception: {
    routeIds: [
      "overview",
      "calendar",
      "patients",
      "work-items",
      "finance",
      "finance-shifts",
      "notifications",
    ],
    serverRouteIds: [
      "overview",
      "calendar",
      "patients",
      "work-items",
      "finance",
      "notifications",
    ],
    forbiddenPaths: ["/inventory", "/analytics", "/team", "/audit", "/settings"],
  },
  admin: {
    routeIds: Object.keys(routeCatalog),
    serverRouteIds: [
      "overview",
      "calendar",
      "patients",
      "work-items",
      "finance",
      "inventory",
      "analytics",
      "notifications",
      "team",
      "audit",
      "settings",
      "password-resets",
      "contracts",
    ],
    forbiddenPaths: [],
  },
};

if (requestedRole && !(requestedRole in roles)) {
  throw new Error(`Unknown TP904_ROLE: ${requestedRole}.`);
}
const selectedRoles = requestedRole ? [requestedRole] : Object.keys(roles);

const viewports = [
  { name: "desktop", width: 1440, height: 900, mobile: false },
  { name: "tablet", width: 1024, height: 768, mobile: false },
  { name: "phone", width: 390, height: 844, mobile: true },
];

const screenshotRoutes = new Set([
  "admin:overview:desktop",
  "admin:inventory:desktop",
  "reception:finance:desktop",
  "reception:overview:phone",
  "podologist:calendar:desktop",
  "podologist:overview:phone",
]);

const results = {
  generated_at: new Date().toISOString(),
  browser: "Microsoft Edge via Playwright",
  base_url: baseUrl,
  roles: {},
  keyboard: [],
  mobile_more: [],
  summary: null,
};

async function csrfToken(context) {
  await context.request.get(`${baseUrl}/api/v1/session`);
  const cookies = await context.cookies(baseUrl);
  const csrf = cookies.find((cookie) => cookie.name === "podoria_csrftoken");
  if (!csrf) throw new Error("CSRF bootstrap cookie is missing.");
  return csrf.value;
}

async function login(context, role) {
  const response = await context.request.post(`${baseUrl}/api/v1/auth/login`, {
    data: credentials[role],
    headers: { "X-CSRFToken": await csrfToken(context) },
  });
  if (response.status() !== 200) throw new Error(`${role} login returned ${response.status()}.`);
  const session = await response.json();
  const actual = [...session.route_ids];
  const expected = roles[role].serverRouteIds;
  if (session.user.role !== role || JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${role} session contract mismatch: ${JSON.stringify(session)}.`);
  }
  return { role: session.user.role, route_ids: actual };
}

async function waitForRoute(page, routeId) {
  const route = routeCatalog[routeId];
  await page.goto(`${baseUrl}${route.path}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: route.heading, exact: true }).waitFor();
  await page.waitForLoadState("networkidle", { timeout: 2_000 }).catch(() => undefined);
}

async function pageMetrics(page) {
  return page.locator("main#main-content").evaluate(() => {
    const sidebar = document.querySelector(".sidebar");
    const mobileNavigation = document.querySelector(".mobile-bottom-nav");
    if (!sidebar || !mobileNavigation) throw new Error("Responsive shell is incomplete.");
    const undersized = Array.from(
      document.querySelectorAll(
        ".mobile-bottom-nav a, .mobile-bottom-nav button, main .button, main .icon-button",
      ),
    )
      .filter((element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== "none"
          && style.visibility !== "hidden"
          && rect.width > 0
          && rect.height > 0
          && (rect.width < 43.5 || rect.height < 43.5);
      })
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          label: element.getAttribute("aria-label") ?? element.textContent?.trim().slice(0, 60),
          width: Math.round(rect.width * 10) / 10,
          height: Math.round(rect.height * 10) / 10,
        };
      });
    return {
      client_width: document.documentElement.clientWidth,
      scroll_width: document.documentElement.scrollWidth,
      sidebar_display: getComputedStyle(sidebar).display,
      mobile_navigation_display: getComputedStyle(mobileNavigation).display,
      undersized_touch_targets: undersized,
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
    return scan.violations
      .filter((violation) => ["serious", "critical"].includes(violation.impact))
      .map((violation) => ({
        id: violation.id,
        impact: violation.impact,
        nodes: violation.nodes.map((node) => node.target),
      }));
  });
}

function assertRouteState(label, metrics, violations, browserErrors, mobile) {
  if (metrics.scroll_width > metrics.client_width) {
    throw new Error(`${label} has page overflow: ${JSON.stringify(metrics)}.`);
  }
  if (mobile) {
    if (metrics.sidebar_display !== "none" || metrics.mobile_navigation_display === "none") {
      throw new Error(`${label} does not use the mobile shell.`);
    }
    if (metrics.undersized_touch_targets.length > 0) {
      throw new Error(`${label} has undersized targets: ${JSON.stringify(metrics)}.`);
    }
  } else if (metrics.sidebar_display === "none" || metrics.mobile_navigation_display !== "none") {
    throw new Error(`${label} does not use the desktop/tablet shell.`);
  }
  if (violations.length > 0) throw new Error(`${label} axe: ${JSON.stringify(violations)}.`);
  if (browserErrors.length > 0) {
    throw new Error(`${label} browser errors: ${JSON.stringify(browserErrors)}.`);
  }
}

async function runRoleViewport(role, viewport) {
  const context = await browser.newContext({ viewport });
  await context.addInitScript({ content: axeSource });
  const session = await login(context, role);
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  let activeRoute = "bootstrap";
  let browserErrors = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      browserErrors.push({ route: activeRoute, message: `${message.type()}: ${message.text()}` });
    }
  });
  page.on("pageerror", (error) => {
    browserErrors.push({ route: activeRoute, message: `pageerror: ${error.message}` });
  });
  const roleResult = { viewport: viewport.name, session, routes: [], forbidden: [] };
  try {
    for (const routeId of roles[role].routeIds) {
      activeRoute = routeId;
      browserErrors = [];
      await waitForRoute(page, routeId);
      const metrics = await pageMetrics(page);
      const violations = await axeViolations(page);
      assertRouteState(`${role}/${viewport.name}/${routeId}`, metrics, violations, browserErrors, viewport.mobile);
      if (screenshotRoutes.has(`${role}:${routeId}:${viewport.name}`)) {
        await page.screenshot({
          fullPage: true,
          path: path.join(evidenceDir, `${role}-${routeId}-${viewport.name}.png`),
        });
      }
      roleResult.routes.push({ route_id: routeId, metrics, axe_violations: violations, browser_errors: browserErrors });
    }
    if (viewport.name === "desktop") {
      for (const forbiddenPath of roles[role].forbiddenPaths) {
        activeRoute = `forbidden:${forbiddenPath}`;
        browserErrors = [];
        await page.goto(`${baseUrl}${forbiddenPath}`, { waitUntil: "domcontentloaded" });
        await page.getByRole("heading", { name: "Добрий день", exact: true }).waitFor();
        const pathname = new URL(page.url()).pathname;
        if (pathname !== "/") throw new Error(`${role} direct URL ${forbiddenPath} remained at ${pathname}.`);
        if (browserErrors.length > 0) throw new Error(`${role} forbidden redirect logged errors.`);
        roleResult.forbidden.push({ requested: forbiddenPath, redirected_to: pathname });
      }
    }
  } finally {
    await context.close();
  }
  return roleResult;
}

async function runKeyboard(role) {
  const context = await browser.newContext({ viewport: viewports[0] });
  await login(context, role);
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  try {
    await waitForRoute(page, "overview");
    await page.keyboard.press("Tab");
    const skipText = await page.evaluate(() => document.activeElement?.textContent?.trim());
    if (skipText !== "До основного вмісту") throw new Error(`${role} skip link is not first.`);
    await page.keyboard.press("Enter");
    const skipTarget = await page.evaluate(() => document.activeElement?.id);
    if (skipTarget !== "main-content") throw new Error(`${role} skip link target mismatch.`);
    const searchTrigger = page.getByRole("button", { name: "Відкрити глобальний пошук" });
    await searchTrigger.focus();
    await page.keyboard.press("Control+K");
    const dialog = page.getByRole("dialog", { name: "Глобальний пошук" });
    await dialog.waitFor();
    const opened = await page.evaluate(() => ({
      focused: document.activeElement?.matches("#global-search-dialog input[type='search']") ?? false,
      body_overflow: document.body.style.overflow,
    }));
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "detached" });
    await page.waitForFunction(
      () => document.activeElement?.getAttribute("aria-label") === "Відкрити глобальний пошук",
      null,
      { timeout: 2_000 },
    );
    const closed = await page.evaluate(() => ({
      trigger_focused: document.activeElement?.getAttribute("aria-label") === "Відкрити глобальний пошук",
      body_overflow: document.body.style.overflow,
    }));
    if (!opened.focused || opened.body_overflow !== "hidden" || !closed.trigger_focused || closed.body_overflow !== "") {
      throw new Error(`${role} search focus lifecycle failed.`);
    }
    return { role, skip_text: skipText, skip_target: skipTarget, opened, closed };
  } finally {
    await context.close();
  }
}

async function runMobileMore(role) {
  const context = await browser.newContext({ viewport: viewports[2] });
  await login(context, role);
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  try {
    await waitForRoute(page, "overview");
    const trigger = page.getByRole("button", { name: "Ще", exact: true });
    await trigger.click();
    const dialog = page.locator(".mobile-more[role='dialog']");
    await dialog.waitFor();
    const links = await dialog.locator(".mobile-more__grid a:visible").allTextContents();
    const opened = await page.evaluate(() => ({
      active_label: document.activeElement?.getAttribute("aria-label"),
      body_overflow: document.body.style.overflow,
    }));
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "detached" });
    await page.waitForFunction(() => document.activeElement?.textContent?.trim() === "Ще");
    const closed = await page.evaluate(() => ({
      trigger_focused: document.activeElement?.textContent?.trim() === "Ще",
      body_overflow: document.body.style.overflow,
    }));
    if (opened.active_label !== "Закрити додаткове меню" || opened.body_overflow !== "hidden") {
      throw new Error(`${role} mobile More open lifecycle failed.`);
    }
    if (!closed.trigger_focused || closed.body_overflow !== "") {
      throw new Error(`${role} mobile More close lifecycle failed.`);
    }
    return { role, links: links.map((value) => value.trim()), opened, closed };
  } finally {
    await context.close();
  }
}

try {
  for (const role of selectedRoles) {
    results.roles[role] = [];
    for (const viewport of viewports) {
      results.roles[role].push(await runRoleViewport(role, viewport));
    }
    results.keyboard.push(await runKeyboard(role));
    results.mobile_more.push(await runMobileMore(role));
  }
  results.summary = {
    roles: selectedRoles.length,
    viewports: viewports.length,
    route_checks: Object.values(results.roles).flatMap((items) => items).reduce(
      (total, item) => total + item.routes.length,
      0,
    ),
    forbidden_redirect_checks: Object.values(results.roles).flatMap((items) => items).reduce(
      (total, item) => total + item.forbidden.length,
      0,
    ),
    serious_or_critical_axe_violations: 0,
    browser_warnings_or_errors: 0,
  };
  await writeFile(
    path.join(evidenceDir, requestedRole ? `browser-gate-${requestedRole}.json` : "browser-gate.json"),
    `${JSON.stringify(results, null, 2)}\n`,
    "utf8",
  );
  console.log(`TP-904 role UAT passed: ${JSON.stringify(results.summary)}.`);
} catch (error) {
  results.failure = error instanceof Error ? error.message : String(error);
  await writeFile(
    path.join(evidenceDir, requestedRole ? `browser-gate-${requestedRole}.json` : "browser-gate.json"),
    `${JSON.stringify(results, null, 2)}\n`,
    "utf8",
  );
  throw error;
} finally {
  await Promise.race([browser.close(), new Promise((resolve) => setTimeout(resolve, 3_000))]);
  setTimeout(() => process.exit(process.exitCode ?? 0), 500);
}
