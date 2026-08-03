import { defineConfig } from "vitepress";
import { copyStaticAssets } from "../scripts/copy-static-assets.mjs";
import { prepareSite } from "../scripts/prepare-site.mjs";
import { researchPdfDevPlugin } from "../scripts/static-pdf-dev-plugin.mjs";

await prepareSite();

const repositorySourceUrl =
  "https://github.com/yao-LLL/marketing-roi-analysis/blob/main/";

function rewriteRepositorySourceLinks(markdown) {
  markdown.core.ruler.after("inline", "repository-source-links", (state) => {
    for (const token of state.tokens) {
      if (token.type !== "inline" || !token.children) continue;
      for (const child of token.children) {
        if (child.type !== "link_open") continue;
        const href = child.attrGet("href");
        if (!href || /^[a-z][a-z0-9+.-]*:/i.test(href)) continue;
        const match = href.match(
          /(?:^|\/)(modules|design-artifacts|_bmad-output)\/(.+)$/,
        );
        if (!match) continue;
        child.attrSet("href", `${repositorySourceUrl}${match[1]}/${match[2]}`);
      }
    }
  });
}

export default defineConfig({
  title: "Marketing ROI Analysis",
  description:
    "Documentation for Multi-Touch Attribution evidence and campaign budget initialization",
  lang: "zh-CN",
  cleanUrls: true,
  lastUpdated: true,
  rewrites: {
    "_site/index.md": "index.md",
    "index.md": "workspace-index.md",
    "README.md": "documentation-index.md",
    "amc_mta/README.md": "amc_mta/index.md",
    "product/README.md": "product/index.md",
    "research/README.md": "research/index.md",
    "research/ab-testing/README.md": "research/ab-testing/index.md",
    "research/amazon/README.md": "research/amazon/index.md",
    "research/amazon/amc/README.md": "research/amazon/amc/index.md",
    "research/amazon/research/README.md": "research/amazon/research/index.md",
    "research/mta/README.md": "research/mta/index.md",
  },
  markdown: {
    math: true,
    config: rewriteRepositorySourceLinks,
  },
  vite: {
    plugins: [researchPdfDevPlugin()],
  },
  buildEnd: copyStaticAssets,
  ignoreDeadLinks: [
    /\.(?:docx|json|txt|drawio)(?:$|[?#])/i,
  ],
  themeConfig: {
    nav: [
      { text: "首页", link: "/" },
      { text: "工作区索引", link: "/workspace-index" },
      { text: "架构", link: "/architecture" },
      { text: "AMC MTA", link: "/amc_mta/" },
      { text: "研究资料", link: "/research/" },
      {
        text: "GitHub",
        link: "https://github.com/yao-LLL/marketing-roi-analysis",
      },
    ],
    sidebar: [
      {
        text: "项目现状",
        items: [
          { text: "工作区总索引", link: "/workspace-index" },
          { text: "工作区总览", link: "/project-overview" },
          { text: "架构", link: "/architecture" },
          { text: "组件清单", link: "/component-inventory" },
          { text: "目录分析", link: "/source-tree-analysis" },
          { text: "开发指南", link: "/development-guide" },
        ],
      },
      {
        text: "AMC MTA",
        items: [
          { text: "模块入口", link: "/amc_mta/" },
          { text: "架构说明", link: "/amc_mta/amc-mta-architecture" },
          {
            text: "能力评价",
            link: "/amc_mta/amc-mta-capability-assessment",
          },
          {
            text: "项目介绍",
            link: "/product/amc-mta/project-introduction",
          },
        ],
      },
      {
        text: "研究资料",
        items: [
          { text: "研究索引", link: "/research/" },
          { text: "MTA 研究", link: "/research/mta/" },
          { text: "A/B 测试", link: "/research/ab-testing/" },
          { text: "Amazon 研究", link: "/research/amazon/" },
          {
            text: "Campaign 数据层级",
            link: "/research/campaign-data-hierarchy",
          },
        ],
      },
    ],
    outline: { level: [2, 3], label: "本页内容" },
    search: { provider: "local" },
    socialLinks: [
      {
        icon: "github",
        link: "https://github.com/yao-LLL/marketing-roi-analysis",
      },
    ],
    footer: {
      message: "Attribution evidence and non-optimized campaign budget initialization.",
      copyright: "Marketing ROI Analysis",
    },
  },
});
