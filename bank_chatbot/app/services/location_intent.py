import re
from typing import NamedTuple


class LocationIntentFlags(NamedTuple):
    has_location_cue: bool
    has_geo_token: bool
    has_in_location_phrase: bool


LOCATION_CUES = ["location", "address", "where", "near", "nearest", "around", "located"]

KNOWN_CITY_TOKENS = [
    "dhaka", "chittagong", "sylhet", "khulna", "rajshahi", "barisal", "rangpur",
    "narayanganj", "gazipur", "mymensingh", "comilla", "jessore", "bogra",
    "cox's bazar", "coxs bazar", "feni", "noakhali", "tangail", "faridpur", "kishoreganj",
]

KNOWN_AREA_TOKENS = [
    "gulshan", "banani", "baridhara", "dhanmondi", "uttara", "motijheel",
    "mirpur", "tejgaon", "basundhara", "badda", "malibagh", "mohakhali",
    "paltan", "farmgate", "elephant road", "new market", "mouchak",
]

IN_LOCATION_PHRASE_RE = re.compile(
    r"\b(in)\s+(?!ebl\b|skybanking\b|app\b|mobile\b|online\b|atm\b|atms\b|crm\b|rtdm\b|branch\b|branches\b)[a-z][a-z0-9\s\-]{2,}\b"
)


def get_location_intent_flags(query: str) -> LocationIntentFlags:
    query_lower = (query or "").lower()
    has_location_cue = any(k in query_lower for k in LOCATION_CUES)
    has_in_location_phrase = bool(IN_LOCATION_PHRASE_RE.search(query_lower))
    has_geo_token = any(tok in query_lower for tok in KNOWN_CITY_TOKENS + KNOWN_AREA_TOKENS)
    return LocationIntentFlags(
        has_location_cue=has_location_cue,
        has_geo_token=has_geo_token,
        has_in_location_phrase=has_in_location_phrase,
    )
