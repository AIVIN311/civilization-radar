#!/usr/bin/env node
import { chromium } from "playwright";
import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

function parseArgs(argv) {
  const opts = {
    dashboard: "output/latest/dashboard_v04.html",
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

async function getVisibleRows(page, selector) {
  return page.locator(selector).evaluateAll((rows) =>
    rows.filter((r) => {
      const style = window.getComputedStyle(r);
      return style.display !== "none" && style.visibility !== "hidden";
    }).length,
  );
}

async function getVisibleDomainRows(page) {
  return getVisibleRows(page, "#domainTable tbody tr");
}

async function getVisibleChainRows(page) {
  return getVisibleRows(page, "#chainTable tbody tr.chain-main");
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

  await page.getByRole("button", { name: "只看 L3", exact: true }).click();
  const l3Count = await getVisibleDomainRows(page);
  summary.checks.push({
    name: "l3_filter_rows",
    ok: l3Count <= baselineCount,
    value: l3Count,
    baseline: baselineCount,
  });

  const shot1 = path.join(outputDir, "02-l3-filter.png");
  await page.screenshot({ path: shot1, fullPage: true });
  summary.screenshots.push(shot1);

  await page.getByRole("button", { name: "全部", exact: true }).click();
  const restoredCount = await getVisibleDomainRows(page);
  summary.checks.push({
    name: "all_filter_restore",
    ok: restoredCount === baselineCount,
    value: restoredCount,
    baseline: baselineCount,
  });

  const profileFilter = page.locator("#profileFilter");
  const hasTwProfile = (await page.locator("#profileFilter option[value='tw']").count()) > 0;
  if (hasTwProfile) {
    await profileFilter.selectOption("tw");
    const chainCount = await getVisibleChainRows(page);
    summary.checks.push({
      name: "profile_filter_rows",
      ok: chainCount > 0,
      value: chainCount,
      profile: "tw",
    });
  } else {
    summary.checks.push({
      name: "profile_filter_rows",
      ok: false,
      skipped: true,
      reason: "No tw profile option",
    });
  }

  const shot2 = path.join(outputDir, "03-profile-filter.png");
  await page.screenshot({ path: shot2, fullPage: true });
  summary.screenshots.push(shot2);

  const top3Button = page.locator("#chainTable tbody tr.chain-main .toggle");
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

  const shot3 = path.join(outputDir, "04-top3-expanded.png");
  await page.screenshot({ path: shot3, fullPage: true });
  summary.screenshots.push(shot3);

  const geoToggle = page.locator("#geoColsToggle");
  if ((await geoToggle.count()) > 0) {
    await geoToggle.uncheck();
    const geoOff = await page.locator("body").evaluate((body) => body.classList.contains("geo-off"));
    summary.checks.push({ name: "geo_toggle_applied", ok: Boolean(geoOff) });
    await geoToggle.check();
  } else {
    summary.checks.push({ name: "geo_toggle_applied", ok: false, skipped: true, reason: "No geo toggle" });
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
