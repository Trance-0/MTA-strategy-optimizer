"""Single source of truth for deterministic simulated touchpoints and Ads inputs."""

from dataclasses import dataclass

from .touchpoint_key import canonical_amc_touchpoint_key


MARKETPLACE = "US"
ADVERTISER_ID = "adv_demo_001"
CURRENCY = "USD"
CAMPAIGN_GROUP_ID = "CG_DEMO_001"


@dataclass(frozen=True)
class TouchpointSpec:
    key: str
    ad_product: str
    ad_type: str
    creative_type: str
    inventory_type: str
    placement: str
    creative_key: str
    interaction_type: str
    billed_interaction: str
    base_impressions: int
    ctr: float
    price: float
    conversion_rate: float
    average_order_value: float
    metric_seed: int

    @property
    def format_value(self) -> str:
        return self.inventory_type if self.ad_product == "AMAZON_DSP" else self.ad_type

    @property
    def cost_type(self) -> str:
        return "CPC" if self.interaction_type == "CLICK" else "CPM"

    def canonical_key(self) -> str:
        return canonical_amc_touchpoint_key(
            self.ad_product,
            self.format_value,
            self.placement,
            self.creative_key,
            self.interaction_type,
        )


def _spec(
    ad_product: str, ad_type: str, creative_type: str, inventory_type: str,
    placement: str, creative_key: str, billed_interaction: str,
    base_impressions: int, ctr: float, price: float, conversion_rate: float,
    average_order_value: float, metric_seed: int, interaction_type: str,
) -> TouchpointSpec:
    format_value = inventory_type if ad_product == "AMAZON_DSP" else ad_type
    key = canonical_amc_touchpoint_key(
        ad_product, format_value, placement, creative_key, interaction_type
    )
    return TouchpointSpec(
        key, ad_product, ad_type, creative_type, inventory_type, placement,
        creative_key, interaction_type, billed_interaction, base_impressions,
        ctr, price, conversion_rate, average_order_value, metric_seed,
    )


_BASE_CONFIGS = (
    ("AMAZON_DSP", "", "", "AUDIO", "UNSPECIFIED", "UNSPECIFIED", "IMPRESSION", 42000, .0022, 18.0, .018, 95.0),
    ("AMAZON_DSP", "", "IMAGE", "DISPLAY", "UNSPECIFIED", "IMAGE", "IMPRESSION", 51000, .0031, 12.5, .020, 105.0),
    ("AMAZON_DSP", "", "VIDEO", "ONLINE_VIDEO", "UNSPECIFIED", "VIDEO", "IMPRESSION", 38000, .0025, 20.0, .021, 118.0),
    ("AMAZON_DSP", "", "VIDEO", "STREAMING_TV", "UNSPECIFIED", "VIDEO", "IMPRESSION", 46000, .0012, 28.0, .025, 132.0),
    ("SPONSORED_BRANDS", "COMPONENT", "IMAGE", "", "TOP_OF_SEARCH", "IMAGE", "CLICK", 18000, .0080, 1.20, .055, 82.0),
    ("SPONSORED_BRANDS", "DISPLAY", "IMAGE", "", "REST_OF_SEARCH", "IMAGE", "CLICK", 21000, .0062, 1.05, .048, 79.0),
    ("SPONSORED_BRANDS", "VIDEO", "VIDEO", "", "TOP_OF_SEARCH", "VIDEO", "CLICK", 16000, .0071, 1.38, .050, 91.0),
    ("SPONSORED_DISPLAY", "DISPLAY", "IMAGE", "", "PRODUCT_PAGE", "IMAGE", "CLICK", 24000, .0058, .92, .045, 76.0),
    ("SPONSORED_DISPLAY", "DISPLAY", "VIDEO", "", "PRODUCT_PAGE", "VIDEO", "CLICK", 19000, .0065, 1.08, .047, 84.0),
    ("SPONSORED_DISPLAY", "VIDEO", "VIDEO", "", "PRODUCT_PAGE", "VIDEO", "CLICK", 17000, .0069, 1.18, .049, 88.0),
    ("SPONSORED_PRODUCTS", "PRODUCT_AD", "", "", "PRODUCT_PAGE", "UNSPECIFIED", "CLICK", 33000, .0105, .88, .075, 68.0),
    ("SPONSORED_PRODUCTS", "PRODUCT_AD", "", "", "REST_OF_SEARCH", "UNSPECIFIED", "CLICK", 36000, .0094, .82, .069, 65.0),
    ("SPONSORED_PRODUCTS", "PRODUCT_AD", "", "", "TOP_OF_SEARCH", "UNSPECIFIED", "CLICK", 40000, .0120, 1.02, .082, 72.0),
)

_INTERACTIONS = (
    ("IMPRESSION",), ("IMPRESSION",), ("IMPRESSION",), ("IMPRESSION",),
    ("IMPRESSION", "CLICK"), ("IMPRESSION",), ("IMPRESSION", "CLICK"),
    ("IMPRESSION", "CLICK"), ("IMPRESSION",), ("CLICK",), ("CLICK",),
    ("CLICK",), ("IMPRESSION", "CLICK"),
)


def _build_catalog() -> tuple[TouchpointSpec, ...]:
    specs = []
    for metric_seed, (config, interactions) in enumerate(
        zip(_BASE_CONFIGS, _INTERACTIONS), start=1
    ):
        specs.extend(_spec(*config, metric_seed, interaction) for interaction in interactions)
    return tuple(specs)


TOUCHPOINT_CATALOG = _build_catalog()
TOUCHPOINT_KEYS = tuple(spec.key for spec in TOUCHPOINT_CATALOG)
EXPECTED_TOUCHPOINT_KEYS = frozenset(
    {
        "AMAZON_DSP:AUDIO:UNSPECIFIED:UNSPECIFIED:IMPRESSION",
        "AMAZON_DSP:DISPLAY:UNSPECIFIED:IMAGE:IMPRESSION",
        "AMAZON_DSP:ONLINE_VIDEO:UNSPECIFIED:VIDEO:IMPRESSION",
        "AMAZON_DSP:STREAMING_TV:UNSPECIFIED:VIDEO:IMPRESSION",
        "SPONSORED_BRANDS:COMPONENT:TOP_OF_SEARCH:IMAGE:IMPRESSION",
        "SPONSORED_BRANDS:COMPONENT:TOP_OF_SEARCH:IMAGE:CLICK",
        "SPONSORED_BRANDS:DISPLAY:REST_OF_SEARCH:IMAGE:IMPRESSION",
        "SPONSORED_BRANDS:VIDEO:TOP_OF_SEARCH:VIDEO:IMPRESSION",
        "SPONSORED_BRANDS:VIDEO:TOP_OF_SEARCH:VIDEO:CLICK",
        "SPONSORED_DISPLAY:DISPLAY:PRODUCT_PAGE:IMAGE:IMPRESSION",
        "SPONSORED_DISPLAY:DISPLAY:PRODUCT_PAGE:IMAGE:CLICK",
        "SPONSORED_DISPLAY:DISPLAY:PRODUCT_PAGE:VIDEO:IMPRESSION",
        "SPONSORED_DISPLAY:VIDEO:PRODUCT_PAGE:VIDEO:CLICK",
        "SPONSORED_PRODUCTS:PRODUCT_AD:PRODUCT_PAGE:UNSPECIFIED:CLICK",
        "SPONSORED_PRODUCTS:PRODUCT_AD:REST_OF_SEARCH:UNSPECIFIED:CLICK",
        "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED:IMPRESSION",
        "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:UNSPECIFIED:CLICK",
    }
)


def validate_touchpoint_catalog(catalog: tuple[TouchpointSpec, ...]) -> None:
    keys = [spec.key for spec in catalog]
    if len(catalog) != 17 or len(set(keys)) != 17:
        raise ValueError("simulated touchpoint catalog must contain exactly 17 unique keys")
    if set(keys) != EXPECTED_TOUCHPOINT_KEYS:
        raise ValueError("simulated touchpoint catalog keys differ from the approved 17-key set")
    invalid = [spec.key for spec in catalog if spec.canonical_key() != spec.key]
    if invalid:
        raise ValueError(f"simulated touchpoint catalog has inconsistent keys: {invalid}")


validate_touchpoint_catalog(TOUCHPOINT_CATALOG)


CAMPAIGN_BY_AD_PRODUCT = {
    "SPONSORED_PRODUCTS": "C_DEMO_SP",
    "SPONSORED_BRANDS": "C_DEMO_SB",
    "SPONSORED_DISPLAY": "C_DEMO_SD",
    "AMAZON_DSP": "C_DEMO_DSP",
}

_KEYWORDS = (
    ("K_RUNNING_EXACT", "running shoes", ("EXACT", "PHRASE")),
    ("K_NIKE_EXACT", "nike running shoes", ("EXACT", "PHRASE")),
    ("K_LIGHTWEIGHT", "lightweight running shoes", ("PHRASE", "BROAD")),
    ("K_TRAIL", "trail running shoes", ("EXACT", "PHRASE")),
    ("K_PREMIUM", "premium running shoes", ("PHRASE", "BROAD")),
    ("K_DISCOVERY", "new running shoe styles", ("BROAD",)),
)

_SKUS = (
    ("SKU_PEG_BLACK", "B0DEMOPEG41B"),
    ("SKU_PEG_WHITE", "B0DEMOPEG41W"),
    ("SKU_TRAIL_BLUE", "B0DEMOTRAILB"),
    ("SKU_VOMERO_RED", "B0DEMOVOMEROR"),
)


def historical_entity_for_touchpoint(spec: TouchpointSpec, variant: int) -> dict[str, str]:
    """Return a deterministic historical entity assignment for a raw event.

    These are observed simulation facts. They do not define the eligible candidate
    pool used by the downstream strategy initializer.
    """
    campaign_id = CAMPAIGN_BY_AD_PRODUCT[spec.ad_product]
    short_name = campaign_id.removeprefix("C_DEMO_")
    sku_id, advertised_asin = _SKUS[(spec.metric_seed + variant) % len(_SKUS)]
    common = {
        "campaign_group_id": CAMPAIGN_GROUP_ID,
        "campaign_id": campaign_id,
        "ad_group_id": f"{campaign_id}_AG{1 + (spec.metric_seed + variant) % 2:02d}",
        "advertised_asin": advertised_asin,
        "sku_id": sku_id,
    }
    if spec.ad_product in {"SPONSORED_PRODUCTS", "SPONSORED_BRANDS"}:
        keyword_id, keyword_text, allowed_matches = _KEYWORDS[
            (spec.metric_seed + variant) % len(_KEYWORDS)
        ]
        match_type = allowed_matches[(spec.metric_seed + variant) % len(allowed_matches)]
        return {
            **common,
            "keyword_id": keyword_id,
            "keyword_text": keyword_text,
            "match_type": match_type,
            "target_id": f"TGT_{short_name}_{keyword_id}_{match_type}",
            "audience_id": "",
        }
    if spec.ad_product == "SPONSORED_DISPLAY":
        return {
            **common,
            "keyword_id": "",
            "keyword_text": "",
            "match_type": "",
            "target_id": f"TGT_SD_PRODUCT_{sku_id}",
            "audience_id": ("AUD_PRODUCT_VIEWERS", "AUD_CATEGORY_INTEREST")[variant % 2],
        }
    return {
        **common,
        "keyword_id": "",
        "keyword_text": "",
        "match_type": "",
        "target_id": f"TGT_DSP_{spec.inventory_type}_{variant % 2 + 1}",
        "audience_id": ("AUD_IN_MARKET_RUNNING", "AUD_LIFESTYLE_FITNESS")[variant % 2],
    }
