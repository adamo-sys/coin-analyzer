"""
Buy Advisor - Rule-based coin purchase recommendations.
Compares a coin against the collection to provide buying advice.
"""

from typing import Dict, Iterable, List, Set, Optional
from dataclasses import dataclass
from acquisition_workflow import AcquisitionWorkflow
from melt_value_engine import MeltValueEngine, ASWReferenceLoader, ManualSpotPriceProvider
from collection_intelligence import GRADE_HIERARCHY
from focused_collection_intelligence import (
    CandidateItem,
    FocusedCollectionIntelligenceEngine,
    MatchStatus,
)


@dataclass
class BuyRecommendation:
    """Buy recommendation result."""
    already_owned: bool
    duplicate_count: int
    upgrade_candidate: bool
    existing_grade: str
    missing_date_in_series: bool
    missing_denomination_in_country: bool
    series_completion: float
    country_completion: float
    base_recommendation: str
    recommendation: str
    reasons: List[str]
    explanation: str
    matching_items: List[Dict]
    max_rational_bid: float
    max_bid_explanation: str
    value_data_available: bool
    value_warning: str
    confidence_score: int
    value_quality: str
    warnings: List[str]
    adam_priority_score: int
    adam_priority_reasons: List[str]
    collection_impact_score: int
    collection_intelligence_factors: List[str]
    liquidity_score: int
    liquidity_reasons: List[str]
    landed_cost: float
    price_verdict: str
    purchase_verdict: str
    estimated_market_value: float
    melt_value_cad: Optional[float] = None
    melt_value_available: bool = False
    spot_price_warning: Optional[str] = None
    acquisition_workflow_result: Optional[Dict] = None


class BuyAdvisor:
    """Rule-based buy advisor for coin collection."""
    
    def __init__(self, collection, staged_want_list_intents: Iterable = None):
        self.collection = collection
        self.staged_want_list_intents = list(staged_want_list_intents or [])
        
        # Initialize melt value engine
        self.asw_loader = ASWReferenceLoader()
        self.spot_provider = ManualSpotPriceProvider(default_spot_price_cad=35.0)
        self.melt_engine = MeltValueEngine(self.asw_loader, self.spot_provider)
    
    def advise(self, country: str, denomination: str, year: str, 
               reference: str = "", numista_n: str = "", grade: str = "",
               asking_price: float = 0.0, shipping: float = 0.0, tax_fees: float = 0.0,
               estimated_market_value: float = 0.0,
               staged_want_list_intents: Iterable = None) -> BuyRecommendation:
        """
        Provide buy recommendation for a coin.
        
        Args:
            country: Coin country
            denomination: Coin denomination
            year: Coin year
            reference: Coin reference (optional)
            numista_n: Numista N# (optional)
            grade: Coin grade (optional)
            asking_price: Asking price (optional)
            shipping: Shipping cost (optional)
            tax_fees: Tax and fees (optional)
            estimated_market_value: Manual estimated market value (optional)
            
        Returns:
            BuyRecommendation with analysis and recommendation
        """
        intelligence_result = self._analyze_candidate_with_intelligence(
            country, denomination, year, reference, grade, staged_want_list_intents
        )
        acquisition_result = self._evaluate_acquisition_workflow(
            country,
            denomination,
            year,
            reference,
            grade,
            asking_price,
            staged_want_list_intents,
        )

        # Check if already owned
        owned_items = self.find_owned_items(country, denomination, year, reference, numista_n)
        already_owned = self._is_owned_status(intelligence_result.match_status) or len(owned_items) > 0
        duplicate_count = len(owned_items)
        
        # Check upgrade candidate
        upgrade_candidate, existing_grade = self.check_upgrade(owned_items, grade, intelligence_result)
        
        # Check series completion
        series_years = self.collection.get_series_years(country, denomination)
        missing_date_in_series = year not in series_years if year else False
        series_completion = len(series_years) / max(len(series_years) + (1 if missing_date_in_series else 0), 1)
        
        # Check country completion
        country_denominations = self.collection.get_country_denominations(country)
        missing_denomination_in_country = denomination not in country_denominations if denomination else False
        country_completion = len(country_denominations) / max(len(country_denominations) + (1 if missing_denomination_in_country else 0), 1)
        
        # Calculate completion impact
        completion_impact = self.calculate_completion_impact(
            missing_date_in_series, missing_denomination_in_country,
            series_completion, country_completion
        )
        
        # Find matching/near-matching items
        matching_items = self.find_matching_items(country, denomination, year, reference, numista_n)
        
        # Check value data availability (check both owned and matching items)
        value_data_available, value_warning = self.check_value_data(owned_items + matching_items, estimated_market_value)
        
        # Generate recommendation with improved logic
        base_recommendation, reasons = self.generate_recommendation(
            already_owned, duplicate_count, upgrade_candidate,
            missing_date_in_series, missing_denomination_in_country,
            completion_impact, grade
        )
        
        # Calculate Adam Priority Score
        adam_priority_score, adam_priority_reasons = self.calculate_adam_priority_score(
            country, denomination, year, reference
        )
        collection_impact_score, collection_intelligence_factors = self.calculate_collection_intelligence_boosts(
            country,
            denomination,
            year,
            reference,
            staged_want_list_intents,
        )
        adam_priority_score += collection_impact_score
        adam_priority_reasons.extend(collection_intelligence_factors)
        
        # Calculate Liquidity Score
        liquidity_score, liquidity_reasons = self.calculate_liquidity_score(
            country, denomination, year, reference
        )
        
        # Adjust recommendation based on Adam Priority Score
        recommendation = self.adjust_recommendation_by_priority(
            base_recommendation, adam_priority_score
        )
        recommendation = self.apply_low_priority_world_guardrail(
            recommendation,
            adam_priority_score,
            collection_impact_score,
            liquidity_score,
        )
        
        # Calculate max rational bid based on recommendation
        max_rational_bid, max_bid_explanation = self.calculate_max_rational_bid(
            recommendation, owned_items + matching_items, value_data_available, estimated_market_value
        )
        
        # Calculate price analysis
        landed_cost, price_verdict = self.calculate_price_analysis(
            asking_price, shipping, tax_fees, max_rational_bid
        )
        
        # Calculate purchase verdict
        purchase_verdict = self.calculate_purchase_verdict(
            recommendation, adam_priority_score, liquidity_score,
            max_rational_bid, landed_cost, price_verdict
        )
        
        # Calculate confidence score
        confidence_score = self.calculate_confidence_score(
            already_owned, matching_items, value_data_available,
            reference, numista_n, year, grade, estimated_market_value
        )
        
        # Classify value quality
        value_quality = self.classify_value_quality(value_data_available, matching_items)
        
        # Generate warnings
        warnings = self.generate_warnings(
            value_data_available, grade, reference, numista_n
        )
        
        # Generate clear explanation
        explanation = self.generate_explanation(
            already_owned, duplicate_count, upgrade_candidate,
            missing_date_in_series, missing_denomination_in_country,
            series_completion, country_completion, completion_impact,
            grade, existing_grade
        )
        
        # Add Adam Priority adjustment explanation if recommendation changed
        if recommendation != base_recommendation:
            if adam_priority_score >= 50:
                explanation += f" Adam Priority adjusted recommendation from {base_recommendation} to {recommendation} because priority score is {adam_priority_score} (50+)."
            elif adam_priority_score < 0:
                explanation += f" Adam Priority adjusted recommendation from {base_recommendation} to {recommendation} because priority score is {adam_priority_score} (below 0)."
        
        # Calculate melt value (supporting factor, won't break if fails)
        melt_value_cad = None
        melt_value_available = False
        spot_price_warning = None
        try:
            melt_result = self.melt_engine.calculate_melt_value(
                country=country,
                denomination=denomination,
                year=year
            )
            melt_value_cad = melt_result.melt_value_cad
            melt_value_available = melt_result.is_silver
            spot_price_warning = melt_result.spot_price_warning
            
            # Add melt value to explanation for silver coins
            if melt_value_available and melt_value_cad > 0:
                explanation += f" Melt value: ${melt_value_cad:.2f} CAD."
                if spot_price_warning:
                    explanation += f" {spot_price_warning}"
        except Exception as e:
            # Melt value calculation failed, continue without it
            pass
        
        return BuyRecommendation(
            already_owned=already_owned,
            duplicate_count=duplicate_count,
            upgrade_candidate=upgrade_candidate,
            existing_grade=existing_grade,
            missing_date_in_series=missing_date_in_series,
            missing_denomination_in_country=missing_denomination_in_country,
            series_completion=series_completion,
            country_completion=country_completion,
            base_recommendation=base_recommendation,
            recommendation=recommendation,
            reasons=reasons,
            explanation=explanation,
            matching_items=matching_items,
            max_rational_bid=max_rational_bid,
            max_bid_explanation=max_bid_explanation,
            value_data_available=value_data_available,
            value_warning=value_warning,
            confidence_score=confidence_score,
            value_quality=value_quality,
            warnings=warnings,
            adam_priority_score=adam_priority_score,
            adam_priority_reasons=adam_priority_reasons,
            collection_impact_score=collection_impact_score,
            collection_intelligence_factors=collection_intelligence_factors,
            liquidity_score=liquidity_score,
            liquidity_reasons=liquidity_reasons,
            landed_cost=landed_cost,
            price_verdict=price_verdict,
            purchase_verdict=purchase_verdict,
            estimated_market_value=estimated_market_value,
            melt_value_cad=melt_value_cad,
            melt_value_available=melt_value_available,
            spot_price_warning=spot_price_warning,
            acquisition_workflow_result=acquisition_result.to_dict(),
        )
    
    def find_owned_items(self, country: str, denomination: str, year: str,
                       reference: str = "", numista_n: str = "") -> List:
        """Find owned items through the focused Collection Intelligence Engine."""
        candidate = CandidateItem(country=country, denomination=denomination, year=year)
        matches = FocusedCollectionIntelligenceEngine(self.collection.items).find_exact_items(candidate)

        for item in self.collection.items:
            # Match by Numista N# if provided
            if numista_n and item.numista_n == numista_n and item not in matches:
                matches.append(item)
                continue
            
            # Match by reference if provided
            if reference and item.reference == reference and item not in matches:
                matches.append(item)
        
        return matches
    
    def check_upgrade(self, owned_items: List, new_grade: str, intelligence_result=None) -> tuple:
        """Check if new coin is an upgrade over existing through Collection Intelligence."""
        if not owned_items or not new_grade:
            return False, ""

        if intelligence_result and intelligence_result.best_existing_match:
            existing_grade = intelligence_result.best_existing_match.grade
            return intelligence_result.match_status == MatchStatus.BETTER_GRADE_UPGRADE, existing_grade
        
        # Get best existing grade
        best_existing_grade = ""
        best_existing_score = 0
        
        for item in owned_items:
            if item.grade and item.grade in GRADE_HIERARCHY:
                score = GRADE_HIERARCHY[item.grade]
                if score > best_existing_score:
                    best_existing_score = score
                    best_existing_grade = item.grade
        
        # Compare with new grade
        if new_grade in GRADE_HIERARCHY:
            new_score = GRADE_HIERARCHY[new_grade]
            if new_score > best_existing_score:
                return True, best_existing_grade
        
        return False, best_existing_grade

    def _analyze_candidate_with_intelligence(
        self,
        country: str,
        denomination: str,
        year: str,
        reference: str = "",
        grade: str = "",
        staged_want_list_intents: Iterable = None,
    ):
        """Analyze duplicate/upgrade status with the focused Collection Intelligence Engine."""
        intents = list(staged_want_list_intents) if staged_want_list_intents is not None else self.staged_want_list_intents
        candidate = CandidateItem(
            country=country,
            denomination=denomination,
            year=year,
            type_series=reference,
            grade=grade,
        )
        return FocusedCollectionIntelligenceEngine(self.collection.items, intents).analyze_candidate(candidate)

    def _evaluate_acquisition_workflow(
        self,
        country: str,
        denomination: str,
        year: str,
        reference: str = "",
        grade: str = "",
        asking_price: float = 0.0,
        staged_want_list_intents: Iterable = None,
    ):
        """Run acquisition workflow as supporting structured context."""
        intents = list(staged_want_list_intents) if staged_want_list_intents is not None else self.staged_want_list_intents
        candidate = CandidateItem(
            country=country,
            denomination=denomination,
            year=year,
            type_series=reference,
            grade=grade,
            asking_price=asking_price,
        )
        return AcquisitionWorkflow(self.collection.items, intents).evaluate(candidate)

    @staticmethod
    def _is_owned_status(match_status) -> bool:
        return match_status in {
            MatchStatus.ALREADY_OWNED,
            MatchStatus.BETTER_GRADE_UPGRADE,
            MatchStatus.SAME_GRADE_DUPLICATE,
            MatchStatus.LOWER_GRADE_DUPLICATE,
        }
    
    def find_matching_items(self, country: str, denomination: str, year: str,
                           reference: str = "", numista_n: str = "") -> List[Dict]:
        """Find matching and near-matching items in collection."""
        matches = []
        
        # Try to parse year for nearby year matching
        target_year = None
        if year:
            try:
                target_year = int(year)
            except (ValueError, TypeError):
                pass
        
        for item in self.collection.items:
            # Exact match
            if (item.country.lower() == country.lower() and
                item.denomination.lower() == denomination.lower() and
                item.year == year):
                matches.append({
                    'match_type': 'exact',
                    'id': item.id,
                    'country': item.country,
                    'denomination': item.denomination,
                    'year': item.year,
                    'grade': item.grade,
                    'reference': item.reference,
                    'numista_n': item.numista_n,
                    'title': item.title,
                    'estimate_cad': item.estimate_cad
                })
            # Same country/denomination, nearby year (near match)
            elif (item.country.lower() == country.lower() and
                  item.denomination.lower() == denomination.lower() and
                  target_year is not None):
                try:
                    item_year = int(item.year) if item.year else None
                    if item_year and abs(item_year - target_year) <= 5:  # Within 5 years
                        matches.append({
                            'match_type': 'near',
                            'id': item.id,
                            'country': item.country,
                            'denomination': item.denomination,
                            'year': item.year,
                            'grade': item.grade,
                            'reference': item.reference,
                            'numista_n': item.numista_n,
                            'title': item.title,
                            'estimate_cad': item.estimate_cad
                        })
                except (ValueError, TypeError):
                    pass
        
        return matches[:10]  # Return top 10 matches
    
    def check_value_data(self, items: List, estimated_market_value: float = 0.0) -> tuple:
        """Check if value/estimate data is available."""
        has_value_data = False
        warning = ""
        
        # Check manual estimated market value first
        if estimated_market_value and estimated_market_value > 0:
            has_value_data = True
            return has_value_data, warning
        
        # Check Numista estimates
        for item in items:
            # Handle both CoinItem objects and dictionaries
            if isinstance(item, dict):
                estimate = item.get('estimate_cad', 0)
            else:
                estimate = item.estimate_cad if hasattr(item, 'estimate_cad') else 0
            
            if estimate and estimate > 0:
                has_value_data = True
                break
        
        if not has_value_data:
            warning = "No estimate/value data available in collection. Max rational bid cannot be calculated."
        
        return has_value_data, warning
    
    def calculate_max_rational_bid(self, recommendation: str, items: List, 
                                   value_data_available: bool, estimated_market_value: float = 0.0) -> tuple:
        """Calculate max rational bid based on recommendation and estimate."""
        # Use manual estimated market value if provided
        if estimated_market_value and estimated_market_value > 0:
            estimate = estimated_market_value
            value_source = "Manual estimate"
        elif value_data_available and items:
            # Get estimate from items (handle both CoinItem objects and dictionaries)
            estimate = 0.0
            for item in items:
                if isinstance(item, dict):
                    item_estimate = item.get('estimate_cad', 0)
                else:
                    item_estimate = item.estimate_cad if hasattr(item, 'estimate_cad') else 0
                
                if item_estimate and item_estimate > 0:
                    estimate = item_estimate
                    value_source = "Numista estimate"
                    break
            if estimate <= 0:
                return 0.0, "No value data available."
        else:
            return 0.0, "No value data available."
        
        # Calculate bid based on recommendation
        if recommendation == "Strong Buy":
            bid = estimate * 0.80
            explanation = f"Max bid is based on Final Recommendation (Strong Buy) and available estimate data."
        elif recommendation == "Buy":
            bid = estimate * 0.70
            explanation = f"Max bid is based on Final Recommendation (Buy) and available estimate data."
        elif recommendation in ["Neutral", "Maybe"]:
            bid = estimate * 0.50
            explanation = f"Max bid is based on Final Recommendation (Neutral) and available estimate data."
        elif recommendation in ["Weak", "Low Priority"]:
            bid = estimate * 0.35
            explanation = f"Max bid is based on Final Recommendation (Low Priority) and available estimate data."
        elif recommendation in ["Duplicate", "Pass"]:
            bid = 0.0
            explanation = f"Not recommended based on Final Recommendation."
        else:
            bid = estimate * 0.50  # Default to 50%
            explanation = f"Max bid is based on Final Recommendation and available estimate data."
        
        return bid, explanation
    
    def calculate_confidence_score(self, already_owned: bool, matching_items: List,
                                   value_data_available: bool, reference: str,
                                   numista_n: str, year: str, grade: str,
                                   estimated_market_value: float = 0.0) -> int:
        """Calculate confidence score (0-100) based on available data."""
        score = 0
        
        # Exact match found (20 points)
        if already_owned:
            score += 20
        
        # Estimate CAD present (20 points)
        # Manual estimate gets 15 points, Numista gets 20 points
        if estimated_market_value and estimated_market_value > 0:
            score += 15  # Manual estimate
        elif value_data_available:
            score += 20  # Numista estimate
        
        # Reference present (15 points)
        if reference:
            score += 15
        
        # Numista N# present (15 points)
        if numista_n:
            score += 15
        
        # Year present (15 points)
        if year:
            score += 15
        
        # Grade present (15 points)
        if grade:
            score += 15
        
        return min(score, 100)
    
    def classify_value_quality(self, value_data_available: bool, matching_items: List) -> str:
        """Classify value quality based on available data."""
        if not value_data_available:
            return "No Value Data"
        
        # Check if matching items have estimates
        has_estimates = False
        for item in matching_items:
            if isinstance(item, dict):
                estimate = item.get('estimate_cad', 0)
            else:
                estimate = item.estimate_cad if hasattr(item, 'estimate_cad') else 0
            
            if estimate and estimate > 0:
                has_estimates = True
                break
        
        if not has_estimates:
            return "Low Confidence"
        
        # Check if multiple items have estimates (higher confidence)
        estimate_count = 0
        for item in matching_items:
            if isinstance(item, dict):
                estimate = item.get('estimate_cad', 0)
            else:
                estimate = item.estimate_cad if hasattr(item, 'estimate_cad') else 0
            
            if estimate and estimate > 0:
                estimate_count += 1
        
        if estimate_count >= 2:
            return "High Confidence"
        else:
            return "Medium Confidence"
    
    def generate_warnings(self, value_data_available: bool, grade: str,
                          reference: str, numista_n: str) -> List[str]:
        """Generate warnings for missing data."""
        warnings = []
        
        if not value_data_available:
            warnings.append("Estimate data missing")
        
        if not grade:
            warnings.append("Grade not specified")
        
        if not reference:
            warnings.append("Reference not specified")
        
        if not numista_n:
            warnings.append("Numista N# not specified")
        
        return warnings
    
    def calculate_adam_priority_score(self, country: str, denomination: str, 
                                      year: str, reference: str) -> tuple:
        """Calculate Adam Priority Score based on strategic criteria."""
        score = 0
        reasons = []
        
        # Newfoundland: +25
        if country and "Newfoundland" in country:
            score += 25
            reasons.append("Newfoundland (+25)")
        
        # Canada key date / recognized variety: +20
        if country and "Canada" in country:
            # Check for key dates (simplified logic)
            if year:
                try:
                    year_int = int(year)
                    # Key dates for Canadian coins (simplified)
                    key_dates = [1911, 1921, 1936, 1947, 1955, 1967]
                    if year_int in key_dates:
                        score += 20
                        reasons.append(f"Canada key date {year} (+20)")
                    # Check for recognized variety in reference
                    if reference and ("variety" in reference.lower() or 
                                     "var" in reference.lower()):
                        score += 20
                        reasons.append("Canada recognized variety (+20)")
                except (ValueError, TypeError):
                    pass
        
        # Canadian silver: +15
        if country and "Canada" in country:
            # Check if denomination suggests silver
            if denomination:
                denom_lower = denomination.lower()
                if "silver" in denom_lower or "dollar" in denom_lower or "50 cent" in denom_lower:
                    score += 15
                    reasons.append("Canadian silver (+15)")
        
        # Canadian pre-1968 circulating coin: +10
        if country and "Canada" in country:
            if year:
                try:
                    year_int = int(year)
                    if year_int < 1968:
                        score += 10
                        reasons.append(f"Canadian pre-1968 ({year}) (+10)")
                except (ValueError, TypeError):
                    pass
        
        # Chartered banknote: +20 if supported by fields
        # This would require additional fields to detect banknotes
        # For now, we'll skip this as it requires more context
        
        # Random world base metal: -10
        if country and "Canada" not in country and "Newfoundland" not in country:
            if denomination:
                denom_lower = denomination.lower()
                if "cent" in denom_lower or "penny" in denom_lower:
                    score -= 10
                    reasons.append("Random world base metal (-10)")
        
        return score, reasons

    def calculate_collection_intelligence_boosts(
        self,
        country: str,
        denomination: str,
        year: str,
        reference: str = "",
        staged_want_list_intents: Iterable = None,
    ) -> tuple:
        """Score collection-intelligence signals without changing price or duplicate logic."""
        score = 0
        factors = []
        intents = list(staged_want_list_intents) if staged_want_list_intents is not None else self.staged_want_list_intents

        if self._matches_want_list_intent(country, denomination, year, reference, intents):
            score += 50
            factors.append("+50 Explicit WANT_LIST target")

        missing_gap, completes_run = self._gap_report_match(country, denomination, year)
        country_lower = (country or "").lower()
        denom_lower = (denomination or "").lower()
        reference_lower = (reference or "").lower()

        if missing_gap:
            if "newfoundland" in country_lower:
                score += 30
                factors.append("+30 Missing Newfoundland date")
            else:
                score += 25
                factors.append("+25 Fills collection gap")

        if completes_run:
            score += 20
            factors.append("+20 Completes date run")

        if "newfoundland" in country_lower:
            score += 25
            factors.append("+25 Newfoundland priority")

        if (
            "canada" in country_lower
            and year == "1859"
            and ("cent" in denom_lower or "large" in denom_lower or "large" in reference_lower)
        ):
            score += 30
            factors.append("+30 1859 Large Cent target")

        if self._matches_generated_want_list_target(country, denomination, year, intents):
            score += 15
            factors.append("+15 Want List Generator target")

        return score, factors

    def _gap_report_match(self, country: str, denomination: str, year: str) -> tuple:
        """Return whether a candidate fills a generated gap and completes a date run."""
        if not country or not denomination or not year:
            return False, False
        try:
            from collection_intelligence import CollectionIntelligenceEngine

            rows = CollectionIntelligenceEngine(self.collection.items).generate_gap_report_rows()
        except Exception:
            return False, False

        for row in rows:
            if (
                self._normalize(row.get("country")) == self._normalize(country)
                and self._normalize(row.get("denomination")) == self._normalize(denomination)
            ):
                missing_years = self._split_years(row.get("missing_years", ""))
                if year in missing_years:
                    return True, len(missing_years) == 1
        return False, False

    def _matches_generated_want_list_target(
        self,
        country: str,
        denomination: str,
        year: str,
        intents: Iterable,
    ) -> bool:
        try:
            from collection_intelligence import CollectionIntelligenceEngine

            targets = CollectionIntelligenceEngine(self.collection.items).generate_want_list(
                limit=25,
                staged_want_list_intents=intents,
            )
        except Exception:
            return False

        candidate = self._candidate_tokens(country, denomination, year)
        for target in targets:
            target_tokens = self._candidate_tokens(target.country, target.denomination, target.year)
            if candidate and candidate == target_tokens:
                return True
        return False

    def _matches_want_list_intent(
        self,
        country: str,
        denomination: str,
        year: str,
        reference: str,
        intents: Iterable,
    ) -> bool:
        candidate_text = " ".join(part for part in [country, denomination, year, reference] if part)
        candidate_tokens = set(self._normalize(candidate_text).split())
        if not candidate_tokens:
            return False

        for intent in intents:
            target_coin = getattr(intent, "target_coin", "")
            target_tokens = set(self._normalize(target_coin).split())
            if target_tokens and target_tokens.issubset(candidate_tokens):
                return True
            if candidate_tokens and candidate_tokens.issubset(target_tokens):
                return True
        return False

    def _candidate_tokens(self, country: str, denomination: str, year: str) -> tuple:
        return tuple(self._normalize(part) for part in [country, denomination, year] if self._normalize(part))

    @staticmethod
    def _split_years(value: str) -> Set[str]:
        years = set()
        for part in str(value or "").replace(";", ",").split(","):
            year = part.strip()
            if year:
                years.add(year)
        return years

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(str(value or "").lower().replace("-", " ").split())
    
    def calculate_liquidity_score(self, country: str, denomination: str, 
                                  year: str, reference: str) -> tuple:
        """Calculate Liquidity Score based on market liquidity factors."""
        score = 0
        reasons = []
        
        # High Liquidity: Newfoundland silver
        if country and "Newfoundland" in country:
            if denomination:
                denom_lower = denomination.lower()
                if "silver" in denom_lower or "50 cent" in denom_lower or "dollar" in denom_lower:
                    score += 25
                    reasons.append("Newfoundland silver (+25)")
                else:
                    score += 10
                    reasons.append("Common Newfoundland (+10)")
        
        # High Liquidity: Canadian key dates
        if country and "Canada" in country:
            if year:
                try:
                    year_int = int(year)
                    key_dates = [1911, 1921, 1936, 1947, 1955, 1967]
                    if year_int in key_dates:
                        score += 25
                        reasons.append(f"Canadian key date {year} (+25)")
                except (ValueError, TypeError):
                    pass
        
        # High Liquidity: Canadian silver
        if country and "Canada" in country:
            if denomination:
                denom_lower = denomination.lower()
                if "silver" in denom_lower or "dollar" in denom_lower or "50 cent" in denom_lower:
                    score += 20
                    reasons.append("Canadian silver (+20)")
        
        # High Liquidity: Chartered banknotes
        # This would require additional fields to detect banknotes
        # For now, we'll skip this as it requires more context
        
        # High Liquidity: UK/Commonwealth silver
        if country and ("United Kingdom" in country or "UK" in country or 
                      "Great Britain" in country or "Australia" in country or 
                      "New Zealand" in country or "South Africa" in country):
            if denomination:
                denom_lower = denomination.lower()
                if "silver" in denom_lower or "shilling" in denom_lower or "crown" in denom_lower:
                    score += 15
                    reasons.append("UK/Commonwealth silver (+15)")
        
        # Medium Liquidity: Canadian base metal
        if country and "Canada" in country:
            if denomination:
                denom_lower = denomination.lower()
                if "cent" in denom_lower or "penny" in denom_lower or "nickel" in denom_lower:
                    score += 10
                    reasons.append("Canadian base metal (+10)")
        
        # Medium Liquidity: better world silver
        if country and "Canada" not in country and "Newfoundland" not in country:
            if denomination:
                denom_lower = denomination.lower()
                if "silver" in denom_lower or "dollar" in denom_lower:
                    score += 5
                    reasons.append("Better world silver (+5)")
        
        # Low Liquidity: common world base metal
        if country and "Canada" not in country and "Newfoundland" not in country:
            if denomination:
                denom_lower = denomination.lower()
                if "cent" in denom_lower or "penny" in denom_lower:
                    score += 0  # Already 0, no reason needed
        
        # Low Liquidity: modern foreign circulation coins (post-2000)
        if country and "Canada" not in country and "Newfoundland" not in country:
            if year:
                try:
                    year_int = int(year)
                    if year_int >= 2000:
                        score -= 5
                        reasons.append(f"Modern foreign circulation coin ({year}) (-5)")
                except (ValueError, TypeError):
                    pass
        
        return score, reasons
    
    def calculate_price_analysis(self, asking_price: float, shipping: float, 
                                tax_fees: float, max_rational_bid: float) -> tuple:
        """Calculate price analysis based on asking price vs max rational bid."""
        # Calculate landed cost
        landed_cost = asking_price + shipping + tax_fees
        
        # If no asking price provided
        if asking_price <= 0:
            return landed_cost, "No asking price entered"
        
        # If no max bid available, cannot price-check
        if max_rational_bid <= 0:
            return landed_cost, "Cannot price-check"
        
        # Calculate difference and percent
        difference = landed_cost - max_rational_bid
        percent_over = (difference / max_rational_bid) * 100 if max_rational_bid > 0 else 0
        
        # Determine price verdict
        if landed_cost < max_rational_bid:
            verdict = "Good price"
        elif landed_cost <= max_rational_bid * 1.10:  # Within 10% over
            verdict = "Borderline"
        else:
            verdict = "Overpriced"
        
        return landed_cost, verdict
    
    def calculate_purchase_verdict(self, recommendation: str, adam_priority_score: int,
                                   liquidity_score: int, max_rational_bid: float,
                                   landed_cost: float, price_verdict: str) -> str:
        """Calculate purchase verdict based on all factors."""
        # Rule 1: If recommendation is Duplicate or Pass → PASS
        if recommendation in ["Duplicate", "Pass"]:
            return "PASS"
        
        # Rule 2: If no asking price provided
        if price_verdict == "No asking price entered":
            # If recommendation is Strong Buy or Buy → BID ONLY
            if recommendation in ["Strong Buy", "Buy"]:
                return "BID ONLY"
            # If recommendation is Neutral or lower → WATCHLIST
            else:
                return "WATCHLIST"
        
        # Rule 3: If cannot price-check (no max bid)
        if price_verdict == "Cannot price-check":
            # If recommendation is Strong Buy or Buy → WATCHLIST
            if recommendation in ["Strong Buy", "Buy"]:
                return "WATCHLIST"
            # If recommendation is Neutral or lower → PASS
            else:
                return "PASS"
        
        # Rule 4: If price is Good price
        if price_verdict == "Good price":
            # If recommendation is Strong Buy → BUY NOW
            if recommendation == "Strong Buy":
                return "BUY NOW"
            # If recommendation is Buy → BUY NOW
            elif recommendation == "Buy":
                return "BUY NOW"
            # If recommendation is Neutral → BID ONLY
            elif recommendation == "Neutral":
                return "BID ONLY"
            # If recommendation is lower → WATCHLIST
            else:
                return "WATCHLIST"
        
        # Rule 5: If price is Borderline
        if price_verdict == "Borderline":
            # If recommendation is Strong Buy → BID ONLY
            if recommendation == "Strong Buy":
                return "BID ONLY"
            # If recommendation is Buy → BID ONLY
            elif recommendation == "Buy":
                return "BID ONLY"
            # If recommendation is Neutral → WATCHLIST
            elif recommendation == "Neutral":
                return "WATCHLIST"
            # If recommendation is lower → PASS
            else:
                return "PASS"
        
        # Rule 6: If price is Overpriced
        if price_verdict == "Overpriced":
            # If recommendation is Strong Buy and priority is high → WATCHLIST
            if recommendation == "Strong Buy" and adam_priority_score >= 50:
                return "WATCHLIST"
            # If recommendation is Strong Buy → PASS
            elif recommendation == "Strong Buy":
                return "PASS"
            # If recommendation is Buy → PASS
            elif recommendation == "Buy":
                return "PASS"
            # If recommendation is Neutral or lower → PASS
            else:
                return "PASS"
        
        # Default: WATCHLIST
        return "WATCHLIST"
    
    def adjust_recommendation_by_priority(self, base_recommendation: str, 
                                         adam_priority_score: int) -> str:
        """Adjust recommendation based on Adam Priority Score."""
        # Rule 1: Do not let priority override Duplicate or Pass
        if base_recommendation in ["Duplicate", "Pass"]:
            return base_recommendation
        
        # Rule 2: If Adam Priority Score is 50+, increase recommendation by one level
        if adam_priority_score >= 50:
            if base_recommendation == "Neutral":
                return "Buy"
            elif base_recommendation == "Buy":
                return "Strong Buy"
            # Strong Buy stays Strong Buy
        
        # Rule 3: If Adam Priority Score is below 0, decrease recommendation by one level
        elif adam_priority_score < 0:
            if base_recommendation == "Strong Buy":
                return "Buy"
            elif base_recommendation == "Buy":
                return "Neutral"
            elif base_recommendation == "Neutral":
                return "Pass"
        
        return base_recommendation

    def apply_low_priority_world_guardrail(
        self,
        recommendation: str,
        adam_priority_score: int,
        collection_impact_score: int,
        liquidity_score: int,
    ) -> str:
        """Prevent low-priority world base metal from becoming buy-now only on price."""
        if recommendation in ["Duplicate", "Pass"]:
            return recommendation

        if (
            adam_priority_score < 0
            and collection_impact_score == 0
            and liquidity_score <= 0
        ):
            return "Neutral"

        return recommendation
    
    def generate_explanation(self, already_owned: bool, duplicate_count: int,
                           upgrade_candidate: bool, missing_date: bool,
                           missing_denom: bool, series_comp: float,
                           country_comp: float, completion_impact: float,
                           grade: str, existing_grade: str) -> str:
        """Generate clear explanation of recommendation."""
        explanation_parts = []
        
        if already_owned:
            if upgrade_candidate:
                explanation_parts.append(f"You already own {duplicate_count} copy(s) of this coin with grade '{existing_grade}'.")
                explanation_parts.append(f"The new coin with grade '{grade}' would be an upgrade.")
                explanation_parts.append("Consider purchasing to improve your collection quality.")
            else:
                explanation_parts.append(f"You already own {duplicate_count} copy(s) of this coin.")
                if duplicate_count > 1:
                    explanation_parts.append("Consider selling duplicates before adding more.")
                else:
                    explanation_parts.append("Unless this is a significant upgrade, you may want to pass.")
        else:
            if missing_date:
                explanation_parts.append(f"This year is missing from your series.")
                explanation_parts.append(f"Adding it would improve your series completion from {series_comp:.1%}.")
            
            if missing_denom:
                explanation_parts.append(f"This denomination is new to your country collection.")
                explanation_parts.append(f"Adding it would expand your country coverage to {country_comp:.1%}.")
            
            if completion_impact >= 0.7:
                explanation_parts.append("This coin fills a significant gap in your collection.")
            elif completion_impact >= 0.4:
                explanation_parts.append("This coin would meaningfully improve your collection.")
            else:
                explanation_parts.append("This coin is an optional addition to your collection.")
        
        return " ".join(explanation_parts)
    
    def calculate_completion_impact(self, missing_date: bool, missing_denom: bool,
                                   series_comp: float, country_comp: float) -> float:
        """Calculate the impact on collection completion."""
        impact = 0.0
        
        # Missing date in series has high impact
        if missing_date:
            impact += 0.4
        
        # Missing denomination in country has medium impact
        if missing_denom:
            impact += 0.3
        
        # Low completion increases impact
        if series_comp < 0.5:
            impact += 0.2
        elif series_comp < 0.8:
            impact += 0.1
        
        if country_comp < 0.5:
            impact += 0.1
        
        return min(impact, 1.0)
    
    def generate_recommendation(self, already_owned: bool, duplicate_count: int,
                               upgrade_candidate: bool, missing_date: bool,
                               missing_denom: bool, completion_impact: float,
                               grade: str) -> tuple:
        """Generate recommendation based on rules."""
        reasons = []
        
        # Rule 1: If already owned and not upgrade -> Duplicate (overrides Buy)
        if already_owned and not upgrade_candidate:
            reasons.append(f"Already own {duplicate_count} copy(s)")
            if duplicate_count > 1:
                reasons.append("Consider selling duplicates")
            return "Duplicate", reasons
        
        # Rule 2: If upgrade candidate -> Buy (overrides Pass)
        if upgrade_candidate:
            reasons.append(f"Upgrade from existing grade")
            return "Buy", reasons
        
        # Rule 3: If already owned and not upgrade -> Pass
        if already_owned:
            reasons.append(f"Already own {duplicate_count} copy(s), no upgrade")
            return "Pass", reasons
        
        # Rule 4: If not owned and high completion impact -> Strong Buy
        if not already_owned and completion_impact >= 0.7:
            reasons.append("Fills significant gap in collection")
            if missing_date:
                reasons.append("Missing date in series")
            if missing_denom:
                reasons.append("New denomination for country")
            return "Strong Buy", reasons
        
        # Rule 5: If not owned and medium completion impact -> Buy
        if not already_owned and completion_impact >= 0.4:
            reasons.append("Adds to collection completeness")
            if missing_date:
                reasons.append("Missing date in series")
            if missing_denom:
                reasons.append("New denomination for country")
            return "Buy", reasons
        
        # Rule 6: If not owned but low impact -> Neutral
        if not already_owned:
            reasons.append("Optional addition to collection")
            return "Neutral", reasons
        
        # Rule 7: Default -> Pass
        reasons.append("Not a priority for current collection")
        return "Pass", reasons


def test_buy_advisor():
    """Test Buy Advisor functionality."""
    from coin_collection import CoinCollection
    
    collection = CoinCollection('data/collection.json')
    advisor = BuyAdvisor(collection)
    
    # First, check what's actually in the collection
    print("=== Sample Collection Items ===")
    for item in collection.items[:3]:
        print(f"  {item.country} {item.denomination} {item.year} - {item.title}")
    
    # Test 1: Coin not in collection
    print("\n=== Test 1: Argentina 1.0 1960 (in collection) ===")
    rec = advisor.advise("Argentina", "1.0", "1960")
    print(f"Already Owned: {rec.already_owned}")
    print(f"Duplicate Count: {rec.duplicate_count}")
    print(f"Upgrade Candidate: {rec.upgrade_candidate}")
    print(f"Missing Date: {rec.missing_date_in_series}")
    print(f"Missing Denomination: {rec.missing_denomination_in_country}")
    print(f"Series Completion: {rec.series_completion:.1%}")
    print(f"Country Completion: {rec.country_completion:.1%}")
    print(f"Base Recommendation: {rec.base_recommendation}")
    print(f"Final Recommendation: {rec.recommendation}")
    print(f"Reasons: {rec.reasons}")
    print(f"Explanation: {rec.explanation}")
    print(f"Matching Items: {len(rec.matching_items)}")
    if rec.matching_items:
        for item in rec.matching_items[:3]:
            print(f"  [{item['match_type']}] {item['country']} {item['denomination']} {item['year']}")
            if item['title']:
                print(f"      Title: {item['title']}")
            if item['numista_n']:
                print(f"      Numista N#: {item['numista_n']}")
            if item['reference']:
                print(f"      Reference: {item['reference']}")
            if item['estimate_cad']:
                print(f"      Estimate: ${item['estimate_cad']:.2f}")
    print(f"Value Data Available: {rec.value_data_available}")
    print(f"Max Rational Bid: ${rec.max_rational_bid:.2f}")
    print(f"Max Bid Explanation: {rec.max_bid_explanation}")
    print(f"Confidence Score: {rec.confidence_score}/100")
    print(f"Value Quality: {rec.value_quality}")
    print(f"Warnings: {rec.warnings}")
    print(f"Adam Priority Score: {rec.adam_priority_score}")
    print(f"Adam Priority Reasons: {rec.adam_priority_reasons}")
    print(f"Liquidity Score: {rec.liquidity_score}")
    print(f"Liquidity Reasons: {rec.liquidity_reasons}")
    print(f"Landed Cost: ${rec.landed_cost:.2f}")
    print(f"Price Verdict: {rec.price_verdict}")
    print(f"Purchase Verdict: {rec.purchase_verdict}")
    print(f"Estimated Market Value: ${rec.estimated_market_value:.2f}")
    if rec.value_warning:
        print(f"Value Warning: {rec.value_warning}")
    
    # Test 2: Coin in collection
    print("\n=== Test 2: Canada 1 cent 1967 (likely in collection) ===")
    rec = advisor.advise("Canada", "1 cent", "1967")
    print(f"Already Owned: {rec.already_owned}")
    print(f"Duplicate Count: {rec.duplicate_count}")
    print(f"Base Recommendation: {rec.base_recommendation}")
    print(f"Final Recommendation: {rec.recommendation}")
    print(f"Reasons: {rec.reasons}")
    print(f"Explanation: {rec.explanation}")
    print(f"Matching Items: {len(rec.matching_items)}")
    print(f"Adam Priority Score: {rec.adam_priority_score}")
    print(f"Adam Priority Reasons: {rec.adam_priority_reasons}")
    print(f"Liquidity Score: {rec.liquidity_score}")
    print(f"Liquidity Reasons: {rec.liquidity_reasons}")
    if rec.matching_items:
        for item in rec.matching_items[:3]:
            print(f"  [{item['match_type']}] {item['country']} {item['denomination']} {item['year']}")
            if item['title']:
                print(f"      Title: {item['title']}")
            if item['numista_n']:
                print(f"      Numista N#: {item['numista_n']}")
            if item['reference']:
                print(f"      Reference: {item['reference']}")
            if item['estimate_cad']:
                print(f"      Estimate: ${item['estimate_cad']:.2f}")
    
    # Test 3: Upgrade candidate
    print("\n=== Test 3: Canada 1 cent 1967 with MS-65 grade ===")
    rec = advisor.advise("Canada", "1 cent", "1967", grade="MS-65")
    print(f"Already Owned: {rec.already_owned}")
    print(f"Upgrade Candidate: {rec.upgrade_candidate}")
    print(f"Existing Grade: {rec.existing_grade}")
    print(f"Base Recommendation: {rec.base_recommendation}")
    print(f"Final Recommendation: {rec.recommendation}")
    print(f"Reasons: {rec.reasons}")
    print(f"Explanation: {rec.explanation}")
    
    # Test 4: Near match with value data (to test bid calculation)
    print("\n=== Test 4: Argentina 20 cents 1975 (near match to 1974) ===")
    rec = advisor.advise("Argentina", "20 cents", "1975")
    print(f"Already Owned: {rec.already_owned}")
    print(f"Duplicate Count: {rec.duplicate_count}")
    print(f"Base Recommendation: {rec.base_recommendation}")
    print(f"Final Recommendation: {rec.recommendation}")
    print(f"Reasons: {rec.reasons}")
    print(f"Explanation: {rec.explanation}")
    print(f"Matching Items: {len(rec.matching_items)}")
    if rec.matching_items:
        for item in rec.matching_items[:3]:
            print(f"  [{item['match_type']}] {item['country']} {item['denomination']} {item['year']}")
            if item['estimate_cad']:
                print(f"      Estimate: ${item['estimate_cad']:.2f}")
    print(f"Value Data Available: {rec.value_data_available}")
    print(f"Max Rational Bid: ${rec.max_rational_bid:.2f}")
    print(f"Max Bid Explanation: {rec.max_bid_explanation}")
    print(f"Adam Priority Score: {rec.adam_priority_score}")
    print(f"Adam Priority Reasons: {rec.adam_priority_reasons}")
    print(f"Liquidity Score: {rec.liquidity_score}")
    print(f"Liquidity Reasons: {rec.liquidity_reasons}")
    print(f"Landed Cost: ${rec.landed_cost:.2f}")
    print(f"Price Verdict: {rec.price_verdict}")
    print(f"Purchase Verdict: {rec.purchase_verdict}")
    print(f"Estimated Market Value: ${rec.estimated_market_value:.2f}")
    
    # Test 5: Manual estimated market value
    print("\n=== Test 5: Manual estimated market value ===")
    rec = advisor.advise("Canada", "1 cent", "1967", estimated_market_value=100.00, asking_price=50.00, shipping=5.00, tax_fees=2.00)
    print(f"Final Recommendation: {rec.recommendation}")
    print(f"Price Verdict: {rec.price_verdict}")
    print(f"Purchase Verdict: {rec.purchase_verdict}")
    print(f"Max Rational Bid: ${rec.max_rational_bid:.2f}")
    print(f"Landed Cost: ${rec.landed_cost:.2f}")
    print(f"Estimated Market Value: ${rec.estimated_market_value:.2f}")
    print(f"Value Data Available: {rec.value_data_available}")
    print(f"Value Quality: {rec.value_quality}")
    print(f"Expected: BUY NOW (Buy + Good price using manual value, Max Bid = $70)")


if __name__ == "__main__":
    test_buy_advisor()
