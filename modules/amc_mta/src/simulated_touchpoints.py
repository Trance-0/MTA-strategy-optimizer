"""Single source of truth for deterministic simulated touchpoints and Ads inputs."""

from dataclasses import dataclass

from touchpoint_key import canonical_amc_touchpoint_key


MARKETPLACE = "US"
ADVERTISER_ID = "adv_demo_001"
CURRENCY = "USD"


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
EXPECTED_TOUCHPOINT_KEYS = frozenset(TOUCHPOINT_KEYS)


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
