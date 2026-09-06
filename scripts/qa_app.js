const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const out = path.join(root, "artifacts", "qa");
fs.mkdirSync(out, { recursive: true });

async function waitForApp(page) {
  await page.goto("http://127.0.0.1:8501", { waitUntil: "domcontentloaded", timeout: 120000 });
  await page.getByText("NeuroChip Copilot", { exact: true }).waitFor({ timeout: 120000 });
  await page.waitForFunction(
    () => document.querySelectorAll('[data-testid="stMetricValue"]').length >= 6,
    null,
    { timeout: 120000 },
  );
  await page.getByRole("button", { name: /下载 PDF 报告/ }).waitFor({ timeout: 120000 });
  await page.waitForTimeout(1800);
}

async function layoutMetrics(page) {
  return page.evaluate(() => ({
    viewportWidth: document.documentElement.clientWidth,
    documentWidth: document.documentElement.scrollWidth,
    plotlyPlots: document.querySelectorAll(".js-plotly-plot").length,
    plotlyMarks: document.querySelectorAll(".js-plotly-plot svg path, .js-plotly-plot svg circle, .js-plotly-plot canvas").length,
  }));
}

async function clickMode(page, name) {
  await page.getByText(name, { exact: true }).click();
  await page.waitForTimeout(1600);
}

async function selectPublicDataset(page, name, expectedRecordText) {
  await page.locator('[data-testid="stSelectbox"]').first().click();
  await page.getByText(name, { exact: true }).last().click();
  await page.waitForFunction(
    ([selectedName, recordText]) => {
      const selectors = document.querySelectorAll('[data-testid="stSelectbox"]');
      return (
        selectors.length >= 2 &&
        selectors[0].textContent.includes(selectedName) &&
        selectors[1].textContent.includes(recordText)
      );
    },
    [name, expectedRecordText],
    { timeout: 120000 },
  );
  await page.getByRole("button", { name: /下载 PDF 报告/ }).waitFor({ timeout: 120000 });
  return page.locator('[data-testid="stSelectbox"]').nth(1).innerText();
}

async function desktopAudit(browser) {
  const pageErrors = [];
  const consoleErrors = [];
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await waitForApp(page);

  const checks = {};
  checks.single = {
    pdfDownload: await page.getByRole("button", { name: /下载 PDF 报告/ }).count(),
    htmlDownload: await page.getByRole("button", { name: /下载 HTML 报告/ }).count(),
    modelExplanationTab: await page.getByText("模型解释", { exact: true }).count(),
    publicDatasetSelector: await page.getByText("公共数据集（仅供示例）", { exact: true }).count(),
    publicRecordSelector: await page.getByText("公开记录", { exact: true }).count(),
    metrics: await layoutMetrics(page),
  };
  await page.getByText("模型解释", { exact: true }).click();
  await page.getByText("系统级验证证据", { exact: true }).waitFor({ timeout: 120000 });
  checks.single.evidenceTable = await page.getByText("系统级验证证据", { exact: true }).count();
  await page.screenshot({ path: path.join(out, "app_evidence.png"), fullPage: true });
  checks.publicSamples = {};
  const publicDatasets = {
    "脑类器官地西泮（19条）": "类器官 2950",
    "GIN二维神经网络（198条）": "人源iPSC二维神经元",
    "Trujillo皮层类器官（72条）": "2016-12-17",
  };
  for (const [dataset, expectedRecordText] of Object.entries(publicDatasets)) {
    checks.publicSamples[dataset] = {
      selectedRecord: await selectPublicDataset(page, dataset, expectedRecordText),
      exceptionCount: await page.locator('[data-testid="stException"]').count(),
    };
  }

  await clickMode(page, "干预评价");
  await page.getByText("多维影响幅度", { exact: true }).waitFor({ timeout: 120000 });
  checks.paired = {
    publicPairDataset: await page.getByText("公共数据集（仅供示例）", { exact: true }).count(),
    publicBaselineSelector: await page.getByText("选择基线记录", { exact: true }).count(),
    publicTreatmentSelector: await page.getByText("选择处理后记录", { exact: true }).count(),
    publicPairResult: await page.getByText("多维影响幅度", { exact: true }).count(),
  };
  await page.screenshot({ path: path.join(out, "app_intervention.png"), fullPage: true });
  await page.getByText("上传数据", { exact: true }).last().click();
  await page.locator('[data-testid="stFileUploader"]').waitFor({ timeout: 120000 });
  await page
    .getByText("请选择公开配对，或上传至少两份记录后指定基线和处理后记录。", { exact: true })
    .waitFor({ timeout: 120000 });
  checks.pairedUpload = {
    multiFileUpload: await page.locator('[data-testid="stFileUploader"]').count(),
    templateDownload: await page.getByRole("button", { name: /下载标准 CSV 模板/ }).count(),
    baselinePrompt: await page
      .getByText("请选择公开配对，或上传至少两份记录后指定基线和处理后记录。", { exact: true })
      .count(),
  };

  await clickMode(page, "项目");
  await page.getByText("项目概览", { exact: true }).waitFor({ timeout: 120000 });
  checks.projects = {
    createProject: await page.getByText("新建项目", { exact: true }).count(),
    projectOverview: await page.getByText("项目概览", { exact: true }).count(),
  };

  await clickMode(page, "单记录");
  await page.getByRole("button", { name: /下载 PDF 报告/ }).waitFor({ timeout: 120000 });
  await page.waitForFunction(() => document.querySelectorAll(".js-plotly-plot").length >= 1, null, { timeout: 120000 });
  await page.screenshot({ path: path.join(out, "app_desktop.png"), fullPage: true });
  const layout = await layoutMetrics(page);
  await page.close();
  return { checks, layout, pageErrors, consoleErrors };
}

async function mobileAudit(browser) {
  const pageErrors = [];
  const consoleErrors = [];
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await waitForApp(page);
  await page.screenshot({ path: path.join(out, "app_mobile.png"), fullPage: true });
  await page.mouse.wheel(0, 6000);
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(out, "app_mobile_bottom.png") });
  const layout = await layoutMetrics(page);
  await page.close();
  return { layout, pageErrors, consoleErrors };
}

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  try {
    const desktop = await desktopAudit(browser);
    const mobile = await mobileAudit(browser);
    const requiredCounts = [
      desktop.checks.single.pdfDownload,
      desktop.checks.single.htmlDownload,
      desktop.checks.single.modelExplanationTab,
      desktop.checks.single.publicDatasetSelector,
      desktop.checks.single.publicRecordSelector,
      desktop.checks.single.evidenceTable,
      desktop.checks.paired.publicPairDataset,
      desktop.checks.paired.publicBaselineSelector,
      desktop.checks.paired.publicTreatmentSelector,
      desktop.checks.paired.publicPairResult,
      desktop.checks.pairedUpload.multiFileUpload,
      desktop.checks.pairedUpload.templateDownload,
      desktop.checks.pairedUpload.baselinePrompt,
      desktop.checks.projects.createProject,
      desktop.checks.projects.projectOverview,
      ...Object.values(desktop.checks.publicSamples).map((item) =>
        item.selectedRecord.length > 0 && item.exceptionCount === 0 ? 1 : 0,
      ),
    ];
    const result = {
      status:
        requiredCounts.every((value) => value > 0) &&
        desktop.layout.documentWidth <= desktop.layout.viewportWidth + 1 &&
        mobile.layout.documentWidth <= mobile.layout.viewportWidth + 1 &&
        desktop.pageErrors.length === 0 &&
        mobile.pageErrors.length === 0 &&
        desktop.consoleErrors.length === 0 &&
        mobile.consoleErrors.length === 0
          ? "pass"
          : "fail",
      desktop,
      mobile,
    };
    fs.writeFileSync(path.join(out, "app_qa.json"), JSON.stringify(result, null, 2) + "\n", "utf8");
    process.stdout.write(JSON.stringify(result, null, 2) + "\n");
    if (result.status !== "pass") process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
