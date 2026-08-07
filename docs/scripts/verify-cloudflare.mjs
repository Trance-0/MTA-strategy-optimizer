import { spawn } from "node:child_process";
import { stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const documentationRoot = resolve(scriptDirectory, "..");
const wranglerEntry = resolve(
  documentationRoot,
  "node_modules",
  "wrangler",
  "bin",
  "wrangler.js",
);
const port = 8791;
const origin = `http://127.0.0.1:${port}`;
const output = [];

const wrangler = spawn(
  process.execPath,
  [wranglerEntry, "dev", "--port", String(port)],
  {
    cwd: documentationRoot,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  },
);
wrangler.stdout.on("data", (chunk) => output.push(chunk.toString()));
wrangler.stderr.on("data", (chunk) => output.push(chunk.toString()));

function delay(milliseconds) {
  return new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
}

async function waitForServer() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(origin);
      if (response.ok) return response;
    } catch {
      // The local Worker is still starting.
    }
    await delay(500);
  }
  throw new Error(`Wrangler did not start.\n${output.join("")}`);
}

try {
  const homeResponse = await waitForServer();
  const home = await homeResponse.text();
  if (!home.includes("Marketing ROI Analysis")) {
    throw new Error("Cloudflare homepage does not contain the generated project title");
  }

  const pdfPath = resolve(
    documentationRoot,
    "research",
    "mta",
    "Data-driven Multi-touch Attribution Models.pdf",
  );
  const expectedPdfSize = (await stat(pdfPath)).size;
  const pdfResponse = await fetch(
    `${origin}/research/mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf`,
  );
  const pdfSize = (await pdfResponse.arrayBuffer()).byteLength;
  if (
    !pdfResponse.ok ||
    pdfResponse.headers.get("content-type") !== "application/pdf" ||
    pdfSize !== expectedPdfSize
  ) {
    throw new Error("Cloudflare did not serve the copied PDF correctly");
  }

  const chinesePlaceholderResponse = await fetch(`${origin}/zh/`);
  const chinesePlaceholder = await chinesePlaceholderResponse.text();
  if (
    !chinesePlaceholderResponse.ok ||
    !chinesePlaceholder.includes("网站正在建设中")
  ) {
    throw new Error("Cloudflare did not serve the Chinese construction placeholder");
  }

  const legacyChineseResponse = await fetch(
    `${origin}/zh/attribution/amc-mta-module`,
  );
  const legacyChinesePage = await legacyChineseResponse.text();
  if (!legacyChineseResponse.ok || !legacyChinesePage.includes("网站正在建设中")) {
    throw new Error("A legacy Chinese route did not serve the construction placeholder");
  }

  const missingResponse = await fetch(`${origin}/definitely-missing-page`);
  if (missingResponse.status !== 404) {
    throw new Error(
      `Cloudflare missing-page response was ${missingResponse.status}, expected 404`,
    );
  }

  console.log(
    JSON.stringify(
      {
        home_status: homeResponse.status,
        pdf_status: pdfResponse.status,
        pdf_content_type: pdfResponse.headers.get("content-type"),
        pdf_bytes: pdfSize,
        chinese_placeholder_status: chinesePlaceholderResponse.status,
        legacy_chinese_route_status: legacyChineseResponse.status,
        missing_page_status: missingResponse.status,
      },
      null,
      2,
    ),
  );
} finally {
  wrangler.kill("SIGTERM");
}
