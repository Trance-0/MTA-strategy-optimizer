import { defineConfig, type DefaultTheme } from "vitepress";
import { copyStaticAssets } from "../scripts/copy-static-assets.mjs";
import { researchPdfDevPlugin } from "../scripts/static-pdf-dev-plugin.mjs";

const repositoryUrl = "https://github.com/Trance-0/marketing-roi-analysis";

const enTheme: DefaultTheme.Config = {
  logoLink: "/en/",
  nav: [
    { text: "Home", link: "/en/" },
    { text: "Overview", link: "/en/introduction/" },
    { text: "Environment", link: "/en/environment/" },
    { text: "Datasets", link: "/en/datasets/" },
    { text: "Attribution", link: "/en/attribution/" },
    { text: "Strategy", link: "/en/strategy/" },
    { text: "Product", link: "/en/product/" },
    { text: "Workspace", link: "/en/workspace/" },
    { text: "Specifications", link: "/en/specifications/" },
    { text: "Research", link: "/en/research/" },
  ],
  sidebar: [
    {
      text: "Introduction",
      items: [
        { text: "Project overview", link: "/en/introduction/" },
        { text: "Structure and pipeline", link: "/en/introduction/project-structure" },
        { text: "Progress and todos", link: "/en/introduction/progress" },
      ],
    },
    {
      text: "Environment setup",
      items: [
        { text: "Local setup and directories", link: "/en/environment/" },
        { text: "Run the AMC MTA module", link: "/en/environment/amc-mta-usage" },
      ],
    },
    {
      text: "Datasets",
      items: [
        { text: "Contracts and compatibility", link: "/en/datasets/" },
        { text: "AMC input data contract", link: "/en/datasets/amc-data-contract" },
        { text: "Amazon Ads sample", link: "/en/datasets/amazon-ads-sample" },
        { text: "AMC simulated data", link: "/en/datasets/amc-simulated-data" },
        { text: "Strategy simulated data", link: "/en/datasets/strategy-simulated-data" },
      ],
    },
    {
      text: "Attribution models",
      items: [
        { text: "Model overview", link: "/en/attribution/" },
        { text: "AMC MTA module", link: "/en/attribution/amc-mta-module" },
        { text: "Complete usage guide", link: "/en/attribution/complete-guide" },
        { text: "Markov removal effect", link: "/en/attribution/markov" },
        { text: "Path-level Shapley", link: "/en/attribution/shapley" },
        { text: "Model testing and comparison", link: "/en/attribution/model-testing" },
        { text: "Standardized MTA interface", link: "/en/attribution/standardized-interface" },
        { text: "DNN credit model", link: "/en/attribution/dnn" },
        { text: "Model comparison governance", link: "/en/attribution/model-governance" },
        { text: "Touchpoint reliability", link: "/en/attribution/reliability" },
        { text: "Output file reference", link: "/en/attribution/output-reference" },
        { text: "Attribution reference index", link: "/en/attribution/reference-index" },
      ],
    },
    {
      text: "Strategy optimization",
      items: [
        { text: "Seed and optimization roadmap", link: "/en/strategy/" },
        { text: "Strategy module", link: "/en/strategy/module-overview" },
        { text: "Current budget calculation", link: "/en/strategy/current-budget-calculation" },
        { text: "Model plan", link: "/en/strategy/model-plan" },
        { text: "Optimization research plan", link: "/en/strategy/optimization-plan" },
        { text: "Output data contract", link: "/en/strategy/output-data-contract" },
        { text: "Strategy output boundary", link: "/en/strategy/strategy-output-contract" },
      ],
    },
    {
      text: "Product and capability",
      items: [
        { text: "Product documentation", link: "/en/product/" },
        { text: "AMC MTA introduction", link: "/en/product/amc-mta/project-introduction" },
        { text: "AMC MTA architecture", link: "/en/product/amc-mta/architecture" },
        { text: "Capability assessment", link: "/en/product/amc-mta/capability-assessment" },
      ],
    },
    {
      text: "Workspace",
      items: [
        { text: "Workspace index", link: "/en/workspace/" },
        { text: "Current assessment", link: "/en/workspace/project-overview" },
        { text: "Workspace architecture", link: "/en/workspace/architecture" },
        { text: "Source-tree analysis", link: "/en/workspace/source-tree-analysis" },
        { text: "File-location rules", link: "/en/workspace/file-management" },
        { text: "Component inventory", link: "/en/workspace/component-inventory" },
        { text: "Development and verification", link: "/en/workspace/development-guide" },
        { text: "Development history", link: "/en/workspace/development-history" },
        { text: "Documentation index", link: "/en/workspace/documentation-index" },
      ],
    },
    {
      text: "Specifications",
      items: [
        { text: "Implementation catalog", link: "/en/specifications/" },
      ],
    },
    {
      text: "Research",
      items: [
        { text: "Research index", link: "/en/research/" },
        { text: "Campaign Group hierarchy", link: "/en/research/campaign-data-hierarchy" },
        { text: "MTA reading order", link: "/en/research/mta/" },
        { text: "MTA model study notes", link: "/en/research/mta/data-driven-mta-models-study-note" },
        { text: "Amazon research", link: "/en/research/amazon/" },
        { text: "Amazon Marketing Cloud", link: "/en/research/amazon/amc/" },
        { text: "AMC, MTA, and ROI flow", link: "/en/research/amazon/amc/data-flow" },
        { text: "Marketing Stream fields", link: "/en/research/amazon/research/amazon-marketing-stream-fields" },
        { text: "Historical technical research", link: "/en/research/amazon/research/technical-amazon-attribution-mta-2026-07-06" },
        { text: "A/B testing reading order", link: "/en/research/ab-testing/" },
      ],
    },
    {
      text: "Reference",
      items: [
        { text: "Definitions", link: "/en/definitions" },
        { text: "Module inventory", link: "/en/reference/module-inventory" },
        { text: "Module and script data flow", link: "/en/reference/data-flow" },
        { text: "Submission manifest", link: "/en/reference/submission-manifest" },
      ],
    },
  ],
  outline: { level: [2, 3], label: "On this page" },
  search: { provider: "local" },
  socialLinks: [{ icon: "github", link: repositoryUrl }],
  footer: {
    message: "Historical attribution evidence, explainable budget seeds, and constrained optimization.",
    copyright: "Marketing ROI Analysis",
  },
};

export default defineConfig({
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
