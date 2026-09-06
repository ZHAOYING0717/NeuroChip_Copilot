const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const ffmpeg = process.env.FFMPEG_PATH;
if (!ffmpeg) {
  throw new Error("FFMPEG_PATH is required");
}

const projectRoot = path.resolve(__dirname, "..");
const outputDir = path.join(projectRoot, "output", "video", "screen");
fs.mkdirSync(outputDir, { recursive: true });
const frameRate = 5;

function startEncoder(outputPath) {
  const child = spawn(
    ffmpeg,
    [
      "-y",
      "-loglevel",
      "warning",
      "-f",
      "image2pipe",
      "-vcodec",
      "mjpeg",
      "-framerate",
      String(frameRate),
      "-i",
      "pipe:0",
      "-an",
      "-c:v",
      "libx264",
      "-preset",
      "medium",
      "-crf",
      "20",
      "-pix_fmt",
      "yuv420p",
      "-r",
      "30",
      outputPath,
    ],
    { stdio: ["pipe", "inherit", "inherit"] },
  );
  return child;
}

async function writeFrame(stream, buffer) {
  if (!stream.write(buffer)) {
    await new Promise((resolve) => stream.once("drain", resolve));
  }
}

async function captureFor(page, encoder, seconds) {
  const frames = Math.round(seconds * frameRate);
  for (let index = 0; index < frames; index += 1) {
    const started = Date.now();
    const frame = await page.screenshot({ type: "jpeg", quality: 84 });
    await writeFrame(encoder.stdin, frame);
    const remaining = 1000 / frameRate - (Date.now() - started);
    if (remaining > 0) {
      await page.waitForTimeout(remaining);
    }
  }
}

async function closeEncoder(encoder) {
  encoder.stdin.end();
  await new Promise((resolve, reject) => {
    encoder.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`ffmpeg exited ${code}`))));
  });
}

async function readyPage(browser) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
  await page.goto("http://127.0.0.1:8501", { waitUntil: "domcontentloaded", timeout: 120000 });
  await page.getByText("NeuroChip Copilot", { exact: true }).waitFor({ timeout: 120000 });
  await page.waitForFunction(() => document.querySelectorAll(".js-plotly-plot").length >= 1, null, { timeout: 120000 });
  await page.waitForTimeout(1800);
  return page;
}

async function recordSingle(browser) {
  const page = await readyPage(browser);
  const encoder = startEncoder(path.join(outputDir, "04_single_screen.mp4"));
  await captureFor(page, encoder, 7.0);
  const tabs = page.locator('[data-baseweb="tab"]');
  await tabs.nth(1).click();
  await page.waitForTimeout(900);
  await captureFor(page, encoder, 8.0);
  await tabs.nth(2).click();
  await page.waitForTimeout(900);
  await captureFor(page, encoder, 8.0);
  await tabs.nth(3).click();
  await page.waitForTimeout(900);
  await captureFor(page, encoder, 8.0);
  await tabs.nth(4).click();
  await page.waitForTimeout(900);
  await page.getByText("系统级验证证据", { exact: true }).scrollIntoViewIfNeeded();
  await captureFor(page, encoder, 12.0);
  await tabs.nth(0).click();
  await page.waitForTimeout(700);
  await captureFor(page, encoder, 6.5);
  await closeEncoder(encoder);
  await page.close();
}

async function recordDrug(browser) {
  const page = await readyPage(browser);
  await page.getByText("干预评价", { exact: true }).click();
  await page.getByText("多维影响幅度", { exact: true }).waitFor({ timeout: 120000 });
  await page.getByText("仅量化影响", { exact: true }).waitFor({ timeout: 120000 });
  await page.getByText("仅量化影响", { exact: true }).last().click();
  await page.getByText("降低过度活动与爆发", { exact: true }).last().click();
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="stMetricValue"]').length >= 6, null, { timeout: 180000 });
  await page.waitForFunction(() => document.querySelectorAll(".js-plotly-plot").length >= 1, null, { timeout: 120000 });
  await page.waitForTimeout(1800);
  const encoder = startEncoder(path.join(outputDir, "06_drug_screen.mp4"));
  await captureFor(page, encoder, 8.0);
  const tabs = page.locator('[data-baseweb="tab"]');
  await tabs.nth(1).click();
  await page.waitForTimeout(700);
  await captureFor(page, encoder, 8.0);
  await tabs.nth(2).click();
  await page.waitForTimeout(700);
  await captureFor(page, encoder, 7.0);
  await tabs.nth(4).click();
  await page.waitForTimeout(700);
  await captureFor(page, encoder, 8.0);
  await tabs.nth(5).click();
  await page.waitForTimeout(700);
  await captureFor(page, encoder, 6.5);
  await tabs.nth(0).click();
  await page.waitForTimeout(700);
  await captureFor(page, encoder, 4.5);
  await closeEncoder(encoder);
  await page.close();
}

(async () => {
  const mode = process.argv[2] || "all";
  if (!["all", "single", "drug"].includes(mode)) {
    throw new Error("Usage: node record_app_demo.js [all|single|drug]");
  }
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  });
  try {
    if (mode === "all" || mode === "single") {
      await recordSingle(browser);
    }
    if (mode === "all" || mode === "drug") {
      await recordDrug(browser);
    }
  } finally {
    await browser.close();
  }
  process.stdout.write(`Recorded app segments in ${outputDir}\n`);
})();
