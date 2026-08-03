import { copyFile, mkdir, readdir } from "node:fs/promises";
import { dirname, extname, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const documentationRoot = resolve(scriptDirectory, "..");
const researchRoot = resolve(documentationRoot, "research");
const outputRoot = resolve(documentationRoot, ".vitepress", "dist");
const copiedResearchExtensions = new Set([".pdf", ".docx", ".json", ".txt"]);

async function findResearchAttachments(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const entryPath = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await findResearchAttachments(entryPath)));
    } else if (
      entry.isFile() &&
      copiedResearchExtensions.has(extname(entry.name).toLowerCase())
    ) {
      files.push(entryPath);
    }
  }
  return files;
}

export async function copyStaticAssets() {
  const attachmentFiles = await findResearchAttachments(researchRoot);
  const rootAttachments = [
    "project-scan-report.json",
    "workspace-file-inventory.json",
    "系统架构图-07.drawio",
  ].map((name) => resolve(documentationRoot, name));
  const staticFiles = [...attachmentFiles, ...rootAttachments];

  for (const sourcePath of staticFiles) {
    const destinationPath = resolve(outputRoot, relative(documentationRoot, sourcePath));
    await mkdir(dirname(destinationPath), { recursive: true });
    await copyFile(sourcePath, destinationPath);
  }

  console.log(
    `[docs] Copied ${staticFiles.length} static documentation files, including ${
      attachmentFiles.filter((path) => extname(path).toLowerCase() === ".pdf").length
    } research PDFs, to ${outputRoot}`,
  );
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await copyStaticAssets();
}
