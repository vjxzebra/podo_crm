import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const evidenceDir = path.resolve(process.cwd(), "../docs/evidence/tp-904");
const expected = {
  podologist: { routes: 15, forbidden: 6 },
  reception: { routes: 21, forbidden: 5 },
  admin: { routes: 39, forbidden: 0 },
};

const combined = {
  generated_at: new Date().toISOString(),
  browser: "Microsoft Edge via Playwright",
  base_url: null,
  roles: {},
  keyboard: [],
  mobile_more: [],
  summary: {
    roles: 0,
    viewports: 3,
    route_checks: 0,
    forbidden_redirect_checks: 0,
    serious_or_critical_axe_violations: 0,
    browser_warnings_or_errors: 0,
  },
};

for (const [role, counts] of Object.entries(expected)) {
  const report = JSON.parse(
    await readFile(path.join(evidenceDir, `browser-gate-${role}.json`), "utf8"),
  );
  if (report.failure) throw new Error(`${role} browser gate failed: ${report.failure}`);
  if (report.summary.roles !== 1 || report.summary.viewports !== 3) {
    throw new Error(`${role} role/viewport summary mismatch.`);
  }
  if (
    report.summary.route_checks !== counts.routes
    || report.summary.forbidden_redirect_checks !== counts.forbidden
    || report.summary.serious_or_critical_axe_violations !== 0
    || report.summary.browser_warnings_or_errors !== 0
  ) {
    throw new Error(`${role} browser summary mismatch: ${JSON.stringify(report.summary)}.`);
  }
  combined.base_url ??= report.base_url;
  if (combined.base_url !== report.base_url) throw new Error("Role reports use different base URLs.");
  combined.roles[role] = report.roles[role];
  combined.keyboard.push(...report.keyboard);
  combined.mobile_more.push(...report.mobile_more);
  combined.summary.roles += 1;
  combined.summary.route_checks += report.summary.route_checks;
  combined.summary.forbidden_redirect_checks += report.summary.forbidden_redirect_checks;
}

if (combined.summary.route_checks !== 75 || combined.summary.forbidden_redirect_checks !== 11) {
  throw new Error(`Combined TP-904 totals are invalid: ${JSON.stringify(combined.summary)}.`);
}

await writeFile(
  path.join(evidenceDir, "browser-gate.json"),
  `${JSON.stringify(combined, null, 2)}\n`,
  "utf8",
);
console.log(`TP-904 browser evidence merged: ${JSON.stringify(combined.summary)}.`);
