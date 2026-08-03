import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const documentationRoot = resolve(scriptDirectory, "..");
const repositoryRoot = resolve(documentationRoot, "..");
const repositoryUrl = "https://github.com/yao-LLL/marketing-roi-analysis";
const generatedDirectory = resolve(documentationRoot, "_site");
const generatedIndex = resolve(generatedDirectory, "index.md");

function githubBlobUrl(repositoryPath) {
  const encodedPath = repositoryPath
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `${repositoryUrl}/blob/main/${encodedPath}`;
}

function siteDocumentationUrl(documentationPath, fragment) {
  const normalizedPath = documentationPath.replaceAll("\\", "/");
  if (normalizedPath === "index.md") {
    return `/workspace-index${fragment}`;
  }
  if (normalizedPath.endsWith(".md")) {
    return `/${normalizedPath.slice(0, -3)}${fragment}`;
  }
  if (normalizedPath.toLowerCase().endsWith(".pdf")) {
    return `/${normalizedPath}${fragment}`;
  }
  return githubBlobUrl(`docs/${normalizedPath}`) + fragment;
}

function rewriteRepositoryLink(rawTarget) {
  if (
    rawTarget.startsWith("#") ||
    rawTarget.startsWith("/") ||
    /^[a-z][a-z0-9+.-]*:/i.test(rawTarget)
  ) {
    return rawTarget;
  }

  const hashPosition = rawTarget.indexOf("#");
  const target = hashPosition === -1 ? rawTarget : rawTarget.slice(0, hashPosition);
  const fragment = hashPosition === -1 ? "" : rawTarget.slice(hashPosition);
  if (target.startsWith("docs/")) {
    return siteDocumentationUrl(target.slice("docs/".length), fragment);
  }
  return githubBlobUrl(target) + fragment;
}

export async function prepareSite() {
  const repositoryReadme = await readFile(resolve(repositoryRoot, "README.md"), "utf8");
  const rewrittenReadme = repositoryReadme.replace(
    /\]\(([^)]+)\)/g,
    (match, target) => `](${rewriteRepositoryLink(target)})`,
  );
  const generatedPage = [
    "---",
    "title: Marketing ROI Analysis",
    "description: Multi-Touch Attribution evidence and campaign budget initialization",
    "---",
    "",
    "<!-- Generated from ../README.md by scripts/prepare-site.mjs. -->",
    "",
    rewrittenReadme,
  ].join("\n");

  await mkdir(generatedDirectory, { recursive: true });
  await writeFile(generatedIndex, generatedPage, "utf8");
  console.log(`[docs] Generated homepage from ${resolve(repositoryRoot, "README.md")}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await prepareSite();
}
