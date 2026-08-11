/**
 * Copy research attachments, audit files, and Chinese placeholder routes into
 * the built documentation site after VitePress renders the English pages.
 */

import { copyFile, mkdir, readdir } from "node:fs/promises";
import { dirname, extname, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const documentationRoot = resolve(scriptDirectory, "..", "docs");
const researchRoot = resolve(documentationRoot, "research");
const chineseSourceRoot = resolve(documentationRoot, "zh");
const publishedDocumentationRoot = resolve(documentationRoot, "en");
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

async function findMarkdownFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const entryPath = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await findMarkdownFiles(entryPath)));
    } else if (entry.isFile() && extname(entry.name).toLowerCase() === ".md") {
      files.push(entryPath);
    }
  }
  return files;
}

async function findFilesByExtension(directory, extensions) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const entryPath = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await findFilesByExtension(entryPath, extensions)));
    } else if (entry.isFile() && extensions.has(extname(entry.name).toLowerCase())) {
      files.push(entryPath);
    }
  }
  return files;
}

export async function copyStaticAssets() {
  const attachmentFiles = await findResearchAttachments(researchRoot);
  const diagramFiles = await findFilesByExtension(
    publishedDocumentationRoot,
    new Set([".drawio", ".svg"]),
  );
  const rootAttachments = [
    "project-scan-report.json",
    "workspace-file-inventory.json",
    "系统架构图-07.drawio",
  ].map((name) => resolve(documentationRoot, name));
  const staticFiles = [
    ...attachmentFiles,
    ...diagramFiles,
    ...rootAttachments,
  ];

  for (const sourcePath of staticFiles) {
    const destinationPath = resolve(outputRoot, relative(documentationRoot, sourcePath));
    await mkdir(dirname(destinationPath), { recursive: true });
    await copyFile(sourcePath, destinationPath);
  }

  const placeholderPage = resolve(outputRoot, "zh", "index.html");
  const preservedChinesePages = await findMarkdownFiles(chineseSourceRoot);
  let mappedChineseRoutes = 0;
  for (const sourcePath of preservedChinesePages) {
    const placeholderRelativePath = relative(chineseSourceRoot, sourcePath).replace(
      /\.md$/i,
      ".html",
    );
    const destinationPath = resolve(outputRoot, "zh", placeholderRelativePath);
    if (destinationPath === placeholderPage) {
      continue;
    }
    await mkdir(dirname(destinationPath), { recursive: true });
    await copyFile(placeholderPage, destinationPath);
    mappedChineseRoutes += 1;
  }

  console.log(
    `[docs] Copied ${staticFiles.length} static documentation files, including ${
      attachmentFiles.filter((path) => extname(path).toLowerCase() === ".pdf").length
    } research PDFs, and mapped ${mappedChineseRoutes} preserved Chinese routes to the construction placeholder in ${outputRoot}`,
  );
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await copyStaticAssets();
}
