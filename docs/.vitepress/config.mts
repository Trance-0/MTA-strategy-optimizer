import { defineConfig, type DefaultTheme } from "vitepress";
import { generateSidebar } from "vitepress-sidebar";
import { copyStaticAssets } from "../../script/copy_static_assets.mjs";
import { researchPdfDevPlugin } from "../../script/static_pdf_dev_plugin.mjs";

const repositoryUrl = "https://github.com/Trance-0/MTA-strategy-optimizer";
const configuredBase = process.env.DOCS_BASE_PATH ?? "/";
const siteBase = configuredBase.endsWith("/") ? configuredBase : `${configuredBase}/`;

const sidebar = generateSidebar([
  {
    documentRootPath: ".",
    scanStartPath: "version",
    resolvePath: "/version/",
    useTitleFromFrontmatter: true,
    useFolderLinkFromIndexFile: true,
    collapsed: true,
    collapseFromLevel: 2,
    rootGroupText: "Version Log",
    rootGroupLink: "/version/",
    sortMenusByFrontmatterOrder: true,
    frontmatterOrderDefaultValue: 100,
  },
  {
    documentRootPath: ".",
    scanStartPath: "worklog",
    resolvePath: "/worklog/",
    useTitleFromFrontmatter: true,
    useFolderLinkFromIndexFile: true,
    collapsed: true,
    collapseFromLevel: 2,
    rootGroupText: "Work Log",
    rootGroupLink: "/worklog/",
    sortMenusByFrontmatterOrder: true,
    frontmatterOrderDefaultValue: 100,
  },
  {
    documentRootPath: ".",
    scanStartPath: "en/introduction",
    resolvePath: "/en/introduction/",
    useTitleFromFrontmatter: true,
    useFolderLinkFromIndexFile: true,
    collapsed: true,
    collapseFromLevel: 2,
    rootGroupText: "Introduction",
    rootGroupLink: "/en/introduction/",
  },
  {
    documentRootPath: ".",
    scanStartPath: "en/environment",
    resolvePath: "/en/environment/",
    useTitleFromFrontmatter: true,
    useFolderLinkFromIndexFile: true,
    collapsed: true,
    collapseFromLevel: 2,
    rootGroupText: "Environment Setup",
    rootGroupLink: "/en/environment/",
  },
  {
    documentRootPath: ".",
    scanStartPath: "en/datasets",
    resolvePath: "/en/datasets/",
    useTitleFromFrontmatter: true,
    useFolderLinkFromIndexFile: true,
    collapsed: true,
    collapseFromLevel: 2,
    rootGroupText: "Datasets",
    rootGroupLink: "/en/datasets/",
  },
  {
    documentRootPath: ".",
    scanStartPath: "en/attribution",
    resolvePath: "/en/attribution/",
    useTitleFromFrontmatter: true,
    useFolderLinkFromIndexFile: true,
    collapsed: true,
    collapseFromLevel: 2,
    rootGroupText: "Attribution Models",
    rootGroupLink: "/en/attribution/",
    // Frontmatter order controls sort within directories
    sortMenusByFrontmatterOrder: true,
    frontmatterOrderDefaultValue: 100,
  },
  {
    documentRootPath: ".",
    scanStartPath: "en/strategy",
    resolvePath: "/en/strategy/",
    useTitleFromFrontmatter: true,
    useFolderLinkFromIndexFile: true,
    collapsed: true,
    collapseFromLevel: 2,
    rootGroupText: "Strategy Optimization",
    rootGroupLink: "/en/strategy/",
  },
  {
    documentRootPath: ".",
    scanStartPath: "en/strategy-evaluation",
    resolvePath: "/en/strategy-evaluation/",
    useTitleFromFrontmatter: true,
    useFolderLinkFromIndexFile: true,
    collapsed: true,
    collapseFromLevel: 2,
    rootGroupText: "Strategy Evaluation",
    rootGroupLink: "/en/strategy-evaluation/",
  },
  {
    documentRootPath: ".",
    scanStartPath: "en/implementation",
    resolvePath: "/en/implementation/",
    useTitleFromFrontmatter: true,
    useFolderLinkFromIndexFile: true,
    collapsed: true,
    collapseFromLevel: 2,
    rootGroupText: "Implementation Reference",
    rootGroupLink: "/en/implementation/",
  },
  {
    documentRootPath: ".",
    scanStartPath: "en/research",
    resolvePath: "/en/research/",
    useTitleFromFrontmatter: true,
    useFolderLinkFromIndexFile: true,
    collapsed: true,
    collapseFromLevel: 2,
    rootGroupText: "Research",
    rootGroupLink: "/en/research/",
  },
  {
    documentRootPath: ".",
    scanStartPath: "en/reference",
    resolvePath: "/en/reference/",
    useTitleFromFrontmatter: true,
    useFolderLinkFromIndexFile: true,
    collapsed: true,
    collapseFromLevel: 2,
    rootGroupText: "Reference",
    rootGroupLink: "/en/reference/",
  },
]);

const enTheme: DefaultTheme.Config = {
  // Unlike normal VitePress navigation links, logoLink is not prefixed with base.
  logoLink: `${siteBase}en/`,
  nav: [
    { text: "Home", link: "/en/" },
    { text: "Overview", link: "/en/introduction/" },
    { text: "Environment", link: "/en/environment/" },
    { text: "Datasets", link: "/en/datasets/" },
    { text: "Attribution", link: "/en/attribution/" },
    { text: "Strategy", link: "/en/strategy/" },
    { text: "Strat. Eval", link: "/en/strategy-evaluation/" },
    { text: "Implementation", link: "/en/implementation/" },
    { text: "Research", link: "/en/research/" },
    { text: "Versions", link: "/version/" },
    { text: "Work Log", link: "/worklog/" },
  ],
  sidebar,
  outline: { level: [2, 3], label: "On this page" },
  search: {
    provider: "local",
    options: {
      detailedView: true,
      miniSearch: {
        options: {
          // Index title, heading hierarchy, and body text
          fields: ["title", "titles", "text"],
          // Store titles for displaying section context in results
          storeFields: ["title", "titles", "text"],
          // Boost matches in titles/headings over body text for accuracy
          boost: { title: 5, titles: 3, text: 1 },
          // Tokenize on camelCase and dots for technical terms
          tokenize: (text: string) =>
            text
              .toLowerCase()
              .split(/[\s,.;:!?()[\]{}"']+/)
              .filter((t: string) => t.length > 0)
              .flatMap((token: string) => [
                token,
                // Also index sub-words split on uppercase for acronyms like "MAE", "RMSE"
                ...token.split(/(?<=[a-z])(?=[A-Z])/),
              ]),
        },
      },
    },
  },
  socialLinks: [{ icon: "github", link: repositoryUrl }],
  footer: {
    message: "Historical attribution evidence, explainable budget seeds, and constrained optimization.",
    copyright: "Marketing ROI Analysis",
  },
};

export default defineConfig({
  base: siteBase,
  title: "Marketing ROI Analysis",
  description:
    "Multi-Touch Attribution evidence and Ad Group budget strategy documentation",
  cleanUrls: true,
  lastUpdated: true,
  themeConfig: enTheme,
  // Preserve Chinese sources for future use, but do not publish them for now.
  srcExclude: ["zh/**", "_site/**"],
  locales: {
    en: {
      label: "English",
      lang: "en-US",
      link: "/en/",
      themeConfig: enTheme,
    },
  },
  rewrites: {
    "zh-placeholder.md": "zh/index.md",
  },
  markdown: {
    math: true,
  },
  vite: { plugins: [researchPdfDevPlugin()] },
  buildEnd: copyStaticAssets,
  ignoreDeadLinks: [/\.(?:docx|json|txt|drawio)(?:$|[?#])/i],
});
