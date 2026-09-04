/**
 * The seven views, their flat navigation order, and their rail icons.
 *
 * This is the single place a view is registered. A page key appears here, in
 * `PAGE_KEYS`, and in `App.vue`'s component map; the test asserts the three
 * agree, so a view cannot be added to
 * the rail without a component behind it.
 *
 * The grouping and the icon set are the reference prototype's
 * (`external/UI_design/brandlens-vue`, by Rouxin Jin), redrawn for this
 * project's seven views.
 */

export const PAGES = {
  overview: {
    title: "Command Center",
    crumb: "AI-MTA / Overview",
    defaultSection: "summary",
    sections: {
      summary: ["shell", "performance", "attribution", "budget"],
    },
    icon: '<path d="M4 4h6v6H4V4zm10 0h6v10h-6V4zM4 14h6v6H4v-6zm10 4h6v2h-6v-2z" stroke="currentColor" stroke-width="1.6"/>',
  },
  generator: {
    title: "Data Generator",
    crumb: "AI-MTA / Data Generator",
    defaultSection: "configure",
    sections: { configure: ["shell"] },
    icon: '<path d="M7 4h10v4H7V4zm-2 7h14v9H5v-9zm4 3h6m-6 3h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
  },
  budget: {
    title: "Budget Manager",
    crumb: "AI-MTA / Planning / Budget",
    defaultSection: "overview",
    sections: {
      overview: ["shell", "budget", "research-overview"],
      providers: ["shell", "research-providers"],
      products: ["shell", "research-products"],
      campaigns: ["shell", "research-campaigns"],
      "ad-groups": ["shell", "research-ad-groups"],
      touchpoints: ["shell", "research-touchpoints"],
      "product-economics": ["shell", "research-product-economics"],
      "generation-configs": ["shell", "research-generation-configs"],
    },
    icon: '<path d="M4 6h16v12H4V6zm0 4h16M8 15h4" stroke="currentColor" stroke-width="1.6"/>',
  },
  campaigns: {
    title: "Campaigns",
    crumb: "AI-MTA / Planning / Campaigns",
    defaultSection: "history",
    sections: {
      history: ["shell", "research-campaign-history"],
      performance: ["shell", "performance"],
      bridge: ["shell", "entity-bridge"],
      paths: ["shell", "path-report"],
    },
    icon: '<path d="M4 12l15-7v14L4 13v-1zm4 3v4l4 1" stroke="currentColor" stroke-width="1.6"/>',
  },
  optimizer: {
    title: "Campaign Optimizer",
    crumb: "AI-MTA / Planning / Optimizer",
    defaultSection: "attribution",
    sections: {
      attribution: ["shell", "attribution"],
      optimization: ["shell", "strategy"],
      evaluation: ["shell", "evaluation"],
    },
    icon: '<path d="M5 17l4-5 3 2 6-8M15 6h3v3" stroke="currentColor" stroke-width="1.7"/>',
  },
  log: {
    title: "Optimization Log",
    crumb: "AI-MTA / Insights / Provenance",
    defaultSection: "provenance",
    sections: {
      provenance: ["shell", "attribution", "budget", "strategy"],
      attribution: ["shell"],
      optimization: ["shell"],
      evaluation: ["shell"],
    },
    icon: '<path d="M5 5h14v14H5V5zm3 4h8m-8 3h8m-8 3h5" stroke="currentColor" stroke-width="1.6"/>',
  },
  knowledge: {
    title: "Knowledge Base",
    crumb: "AI-MTA / Insights / Governance",
    defaultSection: "notice",
    sections: {
      notice: ["shell"],
      "ontology-review": ["shell"],
    },
    icon: '<path d="M4 5h7v14H4V5zm9 0h7v14h-7V5zM7 9h1m8 0h1" stroke="currentColor" stroke-width="1.6"/>',
  },

  // The foot control. It is not a view and is excluded from `PAGE_KEYS`.
  settings: {
    title: "Settings",
    icon:
      '<path d="M12 15.2a3.2 3.2 0 100-6.4 3.2 3.2 0 000 6.4z" stroke="currentColor" stroke-width="1.6"/>' +
      '<path d="M18.7 14.4a1.5 1.5 0 00.3 1.65l.05.06a1.8 1.8 0 11-2.55 2.55l-.05-.06a1.5 1.5 0 00-1.65-.3 1.5 1.5 0 00-.9 1.37v.16a1.8 1.8 0 11-3.6 0v-.09a1.5 1.5 0 00-.98-1.37 1.5 1.5 0 00-1.65.3l-.06.06a1.8 1.8 0 11-2.55-2.55l.06-.06a1.5 1.5 0 00.3-1.65 1.5 1.5 0 00-1.38-.9h-.15a1.8 1.8 0 010-3.6h.09a1.5 1.5 0 001.37-.98 1.5 1.5 0 00-.3-1.65l-.06-.06a1.8 1.8 0 112.55-2.55l.06.06a1.5 1.5 0 001.65.3h.07a1.5 1.5 0 00.9-1.38v-.15a1.8 1.8 0 013.6 0v.09a1.5 1.5 0 00.9 1.37 1.5 1.5 0 001.65-.3l.06-.06a1.8 1.8 0 112.55 2.55l-.06.06a1.5 1.5 0 00-.3 1.65v.07a1.5 1.5 0 001.38.9h.15a1.8 1.8 0 010 3.6h-.09a1.5 1.5 0 00-1.37.9z" stroke="currentColor" stroke-width="1.35"/>',
  },
};

/** Every navigable page key in the rail's one-column order. */
export const PAGE_KEYS = [
  "overview",
  "generator",
  "budget",
  "campaigns",
  "optimizer",
  "log",
  "knowledge",
];

export const DEFAULT_PAGE = PAGE_KEYS[0];

/** Every resource key the browser may request. Mirrors the backend allow-list. */
export const DASHBOARD_RESOURCES = Object.freeze([
  "shell",
  "performance",
  "attribution",
  "budget",
  "strategy",
  "evaluation",
  "entity-bridge",
  "path-report",
  "research-overview",
  "research-providers",
  "research-products",
  "research-campaigns",
  "research-ad-groups",
  "research-touchpoints",
  "research-product-economics",
  "research-generation-configs",
  "research-campaign-history",
]);

/**
 * The resources whose payload depends on the requested history window.
 *
 * Mirrors `WINDOWED_FIELDS` in `backend/repository/snapshot.py`. These are the
 * two resources carrying observation arrays; every other one ignores a window,
 * so requesting them with bounds would only fragment their cache entry.
 */
export const WINDOWED_RESOURCES = Object.freeze(
  new Set(["research-overview", "research-campaign-history"]),
);

/** Normalize a location hash to one declared page and subsection. */
export function parseRoute(hash) {
  const parts = String(hash ?? "")
    .replace(/^#\/?/, "")
    .split("/")
    .filter(Boolean);
  const page = PAGE_KEYS.includes(parts[0]) ? parts[0] : DEFAULT_PAGE;
  const declared = PAGES[page];
  const section = Object.hasOwn(declared.sections, parts[1])
    ? parts[1]
    : declared.defaultSection;
  return { page, section };
}

/** Serialize a validated route in the canonical deep-link form. */
export function routeHash(page, section = PAGES[page]?.defaultSection) {
  const normalized = parseRoute(`#/${page}/${section}`);
  return `#/${normalized.page}/${normalized.section}`;
}

/** Resource keys required to render one validated route. */
export function routeResources(page, section) {
  const normalized = parseRoute(`#/${page}/${section}`);
  return [...PAGES[normalized.page].sections[normalized.section]];
}

/** Where the app points a reader who wants the source or the specification. */
export const REPO_URL = "https://github.com/Trance-0/MTA-strategy-optimizer";
export const DOCS_URL = "https://trance-0.github.io/MTA-strategy-optimizer/docs";
