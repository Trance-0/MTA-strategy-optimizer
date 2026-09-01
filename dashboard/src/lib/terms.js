/** Plain-language help and precise English documentation links for key terms. */
const DEFINITIONS = "/en/reference/definitions";

const TERMS = [
  {
    aliases: ["ROAS", "Blended ROAS"],
    definition: "Return on Ad Spend: reported revenue divided by advertising spend.",
    href: `${DEFINITIONS}#roas-return-on-ad-spend`,
  },
  {
    aliases: ["CTR", "Click-through rate"],
    definition: "Click-Through Rate: clicks divided by impressions that share a valid denominator.",
    href: `${DEFINITIONS}#ctr-click-through-rate`,
  },
  {
    aliases: ["CPC"],
    definition: "Cost Per Click: advertising cost assigned to a click interaction.",
    href: `${DEFINITIONS}#cpc-cost-per-click`,
  },
  {
    aliases: ["CPM"],
    definition: "Cost Per Mille: advertising cost per thousand impressions.",
    href: `${DEFINITIONS}#cpm-cost-per-mille--cost-per-thousand-impressions`,
  },
  {
    aliases: ["MTA attribution", "Attribution", "Attributed revenue"],
    definition: "Multi-Touch Attribution distributes an outcome across touchpoints on observed paths.",
    href: `${DEFINITIONS}#mta-multi-touch-attribution`,
  },
  {
    aliases: ["Touchpoint", "Touchpoints"],
    definition: "One normalized advertising interaction identified by product, format, placement, creative, and interaction type.",
    href: `${DEFINITIONS}#touchpoint`,
  },
  {
    aliases: ["Reliability", "Verdict"],
    definition: "The governed result of arithmetic validity, data support, and model agreement checks.",
    href: `${DEFINITIONS}#reliability`,
  },
  {
    aliases: ["Configured budget"],
    definition: "The authorized spend ceiling for a Campaign and reporting period.",
    href: "/en/strategy-recommendation/campaign-budget-optimizer",
  },
  {
    aliases: ["Actual spend"],
    definition: "The advertising cost delivered within a configured budget and reporting period.",
    href: "/en/strategy-recommendation/campaign-budget-optimizer",
  },
  {
    aliases: ["Contribution profit", "Contribution margin"],
    definition: "Revenue after cost of goods and configured variable fulfillment, platform, and other costs.",
    href: `${DEFINITIONS}#contribution-margin`,
  },
  {
    aliases: ["Conversion path", "Conversion paths", "Path"],
    definition: "An ordered sequence of normalized touchpoints joined with a greater-than separator.",
    href: "/en/market-simulation/index",
  },
  {
    aliases: ["Schema", "Database schema", "Dashboard schema"],
    definition: "A PostgreSQL namespace containing one self-consistent set of dashboard tables.",
    href: `${DEFINITIONS}#database-schema`,
  },
  {
    aliases: ["Ground truth", "Simulation ground truth"],
    definition: "Evaluation-only reference outcomes produced by the synthetic mechanism; never a training feature.",
    href: `${DEFINITIONS}#ground-truth`,
  },
];

const TERM_INDEX = new Map(
  TERMS.flatMap((term) => term.aliases.map((alias) => [alias.toLowerCase(), term])),
);

/** Return the declared term matching one visible label, or null. */
export function termFor(label) {
  return TERM_INDEX.get(String(label ?? "").trim().toLowerCase()) ?? null;
}

/** Exposed for source-level verification of exact documentation paths. */
export const TERM_HELP = Object.freeze(TERMS);
