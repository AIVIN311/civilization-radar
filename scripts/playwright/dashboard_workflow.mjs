#!/usr/bin/env node
import { chromium } from "playwright";
import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

function parseArgs(argv) {
  const opts = {
    dashboard: "output/dashboard_v04.html",
    outputDir: path.join("output", "playwright"),
    headed: false,
    slowMo: 0,
    timeoutMs: 20000,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--dashboard") {
      opts.dashboard = argv[i + 1];
      i += 1;
    } else if (arg === "--output") {
      opts.outputDir = argv[i + 1];
      i += 1;
    } else if (arg === "--headed") {
      opts.headed = true;
    } else if (arg === "--slow-mo") {
      opts.slowMo = Number(argv[i + 1] || "0");
      i += 1;
    } else if (arg === "--timeout") {
      opts.timeoutMs = Number(argv[i + 1] || "20000");
      i += 1;
    }
  }

  return opts;
}

async function getVisibleDomainRows(page) {
  return page.locator("#domainTable tbody tr").evaluateAll((rows) =>
    rows.filter((r) => {
      const style = window.getComputedStyle(r);
      return style.display !== "none" && style.visibility !== "hidden";
    }).length,
  );
}

async function clickIfVisible(locator) {
  const count = await locator.count();
  if (!count) return false;
  await locator.first().click();
  return true;
}

async function launchBrowser(opts) {
  const common = {
    headless: !opts.headed,
    slowMo: opts.slowMo,
  };

  try {
    const browser = await chromium.launch(common);
    return { browser, launcher: "playwright-managed-chromium" };
  } catch (err) {
    const message = String(err?.message || "");
    if (!message.includes("Executable doesn't exist")) {
      throw err;
    }
  }

  const candidates = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ];

  for (const executablePath of candidates) {
    if (!fsSync.existsSync(executablePath)) continue;
    try {
      const browser = await chromium.launch({ ...common, executablePath });
      return { browser, launcher: executablePath };
    } catch {
      // Try next installed browser binary.
    }
  }

  throw new Error(
    "No Playwright browser executable found. Run `npx playwright install chromium` or install Chrome/Edge.",
  );
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const dashboardPath = path.resolve(opts.dashboard);
  const outputDir = path.resolve(opts.outputDir);

  await fs.mkdir(outputDir, { recursive: true });

  const { browser, launcher } = await launchBrowser(opts);
  const context = await browser.newContext({ viewport: { width: 1600, height: 1100 } });
  const page = await context.newPage();
  page.setDefaultTimeout(opts.timeoutMs);

  const summary = {
    dashboardPath,
    outputDir,
    launcher,
    startedAt: new Date().toISOString(),
    checks: [],
    screenshots: [],
  };

  const url = pathToFileURL(dashboardPath).toString();
  await page.goto(url, { waitUntil: "domcontentloaded" });

  await page.locator("#domainTable").waitFor();
  summary.checks.push({ name: "domain_table_visible", ok: true });

  const baselineCount = await getVisibleDomainRows(page);
  summary.checks.push({ name: "baseline_visible_rows", ok: baselineCount > 0, value: baselineCount });

  const shot0 = path.join(outputDir, "01-initial.png");
  await page.screenshot({ path: shot0, fullPage: true });
  summary.screenshots.push(shot0);

  await page.getByRole("button", { name: "事件", exact: true }).click();
  const eventCount = await getVisibleDomainRows(page);
  summary.checks.push({
    name: "event_filter_rows",
    ok: eventCount > 0 && eventCount <= baselineCount,
    value: eventCount,
  });

  const shot1 = path.join(outputDir, "02-event-filter.png");
  await page.screenshot({ path: shot1, fullPage: true });
  summary.screenshots.push(shot1);

  const search = page.locator("#search");
  await search.fill("algorithmicallocation");
  const searchCount = await getVisibleDomainRows(page);
  summary.checks.push({
    name: "search_filter_rows",
    ok: searchCount > 0,
    value: searchCount,
  });

  const shot2 = path.join(outputDir, "03-search.png");
  await page.screenshot({ path: shot2, fullPage: true });
  summary.screenshots.push(shot2);

  const firstMatch = page.locator("#domainTable tbody tr .match:visible");
  const expandedMatch = await clickIfVisible(firstMatch);
  if (expandedMatch) {
    const firstBox = page.locator("#domainTable tbody tr .matchbox:visible");
    const visibleBoxes = await firstBox.count();
    summary.checks.push({ name: "matchbox_expand", ok: visibleBoxes > 0, value: visibleBoxes });
  } else {
    summary.checks.push({ name: "matchbox_expand", ok: false, skipped: true, reason: "No visible match control" });
  }

  const shot3 = path.join(outputDir, "04-match-expanded.png");
  await page.screenshot({ path: shot3, fullPage: true });
  summary.screenshots.push(shot3);

  await search.fill("");
  await page.getByRole("button", { name: "全部", exact: true }).click();

  const stormBtn = page.locator("#stormToggle");
  const hasStorm = (await stormBtn.count()) > 0;
  if (hasStorm) {
    const seriesRows = page.locator("tr.series-row");
    const before = await seriesRows.evaluateAll((rows) =>
      rows.filter((r) => window.getComputedStyle(r).display !== "none").length,
    );
    await stormBtn.click();
    const after = await seriesRows.evaluateAll((rows) =>
      rows.filter((r) => window.getComputedStyle(r).display !== "none").length,
    );
    summary.checks.push({ name: "storm_toggle_applied", ok: after <= before, before, after });
  } else {
    summary.checks.push({ name: "storm_toggle_applied", ok: false, skipped: true, reason: "No storm button" });
  }

  const top3Button = page.locator(".top3-btn");
  if ((await top3Button.count()) > 0) {
    const firstTop3 = top3Button.first();
    const targetId = await firstTop3.getAttribute("data-target");
    await firstTop3.click();
    const isVisible = targetId
      ? await page.locator(`#${targetId}`).evaluate((r) => window.getComputedStyle(r).display === "table-row")
      : false;
    summary.checks.push({ name: "top3_expand", ok: Boolean(isVisible), targetId: targetId || "" });
  } else {
    summary.checks.push({ name: "top3_expand", ok: false, skipped: true, reason: "No top3 buttons in this dashboard" });
  }

  const shot4 = path.join(outputDir, "05-final.png");
  await page.screenshot({ path: shot4, fullPage: true });
  summary.screenshots.push(shot4);

  summary.passed = summary.checks.every((c) => c.ok || c.skipped);
  summary.finishedAt = new Date().toISOString();

  const summaryPath = path.join(outputDir, "dashboard-workflow-summary.json");
  await fs.writeFile(summaryPath, `${JSON.stringify(summary, null, 2)}\n`, "utf8");

  await context.close();
  await browser.close();

  if (!summary.passed) {
    throw new Error(`Workflow failed. See ${summaryPath}`);
  }

  console.log(`Workflow complete. Summary: ${summaryPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
