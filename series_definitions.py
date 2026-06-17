"""Extendable series definitions for collection tracking."""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class SeriesDefinition:
    key: str
    name: str
    country: str
    denomination_terms: Tuple[str, ...]
    priority_base: int = 30
    year_min: Optional[int] = None
    year_max: Optional[int] = None

    def matches(self, country: str, denomination: str, year: str = "") -> bool:
        country_text = (country or "").lower()
        denomination_text = (denomination or "").lower()
        if self.country.lower() not in country_text:
            return False
        if not any(term in denomination_text for term in self.denomination_terms):
            return False
        parsed_year = self.parse_year(year)
        if parsed_year is not None:
            if self.year_min is not None and parsed_year < self.year_min:
                return False
            if self.year_max is not None and parsed_year > self.year_max:
                return False
        return True

    @staticmethod
    def parse_year(year: str) -> Optional[int]:
        try:
            return int(str(year).strip())
        except (TypeError, ValueError):
            return None


SERIES_DEFINITIONS = (
    SeriesDefinition("newfoundland_5_cents", "Newfoundland 5 Cents", "Newfoundland", ("5 cents", "5 cent"), 75),
    SeriesDefinition("newfoundland_10_cents", "Newfoundland 10 Cents", "Newfoundland", ("10 cents", "10 cent", "dime"), 75),
    SeriesDefinition("newfoundland_20_cents", "Newfoundland 20 Cents", "Newfoundland", ("20 cents", "20 cent"), 80),
    SeriesDefinition("newfoundland_50_cents", "Newfoundland 50 Cents", "Newfoundland", ("50 cents", "50 cent", "half"), 85),
    SeriesDefinition("newfoundland_1_cent", "Newfoundland 1 Cent", "Newfoundland", ("1 cent", "large cent", "cent"), 65),
    SeriesDefinition("canadian_large_cents", "Canadian Large Cents", "Canada", ("1 cent", "large cent", "cent"), 70, None, 1920),
    SeriesDefinition("canadian_small_cents", "Canadian Small Cents", "Canada", ("1 cent", "small cent", "cent"), 45, 1920, None),
    SeriesDefinition("canadian_silver_dollars", "Canadian Silver Dollars", "Canada", ("dollar", "silver dollar"), 65),
)
