"""Upgrade Advisor for evaluating candidate coins against existing collection."""

import csv
from dataclasses import dataclass
from typing import Dict, List, Optional
from collection_intelligence import (
    GRADE_HIERARCHY,
    SILVER_DENOMINATION_TERMS,
    NEWFOUNDLAND_FOCUS_TERMS,
)
from focused_collection_intelligence import (
    CandidateItem,
    FocusedCollectionIntelligenceEngine,
)
from melt_value_engine import MeltValueEngine, ASWReferenceLoader, ManualSpotPriceProvider


@dataclass
class UpgradeRecommendation:
    """Upgrade recommendation for a candidate coin."""
    candidate_country: str
    candidate_denomination: str
    candidate_year: str
    candidate_grade: str
    candidate_estimate: float
    
    existing_country: str
    existing_denomination: str
    existing_year: str
    existing_grade: str
    existing_estimate: float
    existing_item_id: str
    
    verdict: str  # Strong Upgrade, Upgrade, Hold Existing, Duplicate, Pass
    upgrade_score: int
    grade_improvement: int  # Grade hierarchy difference
    value_improvement: float  # Value difference
    reason: str
    explanation: str
    candidate_melt_value_cad: Optional[float] = None
    existing_melt_value_cad: Optional[float] = None
    melt_value_improvement: Optional[float] = None
    spot_price_warning: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "candidate_country": self.candidate_country,
            "candidate_denomination": self.candidate_denomination,
            "candidate_year": self.candidate_year,
            "candidate_grade": self.candidate_grade,
            "candidate_estimate": self.candidate_estimate,
            "existing_country": self.existing_country,
            "existing_denomination": self.existing_denomination,
            "existing_year": self.existing_year,
            "existing_grade": self.existing_grade,
            "existing_estimate": self.existing_estimate,
            "existing_item_id": self.existing_item_id,
            "verdict": self.verdict,
            "upgrade_score": self.upgrade_score,
            "grade_improvement": self.grade_improvement,
            "value_improvement": self.value_improvement,
            "reason": self.reason,
            "explanation": self.explanation,
            "candidate_melt_value_cad": self.candidate_melt_value_cad,
            "existing_melt_value_cad": self.existing_melt_value_cad,
            "melt_value_improvement": self.melt_value_improvement,
            "spot_price_warning": self.spot_price_warning,
        }


class UpgradeAdvisor:
    """Evaluates candidate coins against existing collection for upgrade potential."""
    
    def __init__(self, collection_items: List):
        """Initialize with collection items."""
        self.collection_items = collection_items
        
        # Initialize melt value engine
        self.asw_loader = ASWReferenceLoader()
        self.spot_provider = ManualSpotPriceProvider(default_spot_price_cad=35.0)
        self.melt_engine = MeltValueEngine(self.asw_loader, self.spot_provider)
    
    def analyze_upgrade(
        self,
        candidate_country: str,
        candidate_denomination: str,
        candidate_year: str,
        candidate_grade: str = "",
        candidate_estimate: float = 0.0,
    ) -> UpgradeRecommendation:
        """
        Analyze whether a candidate coin is an upgrade over existing collection.
        
        Args:
            candidate_country: Candidate coin country
            candidate_denomination: Candidate coin denomination
            candidate_year: Candidate coin year
            candidate_grade: Candidate coin grade
            candidate_estimate: Candidate coin estimated value
            
        Returns:
            UpgradeRecommendation with verdict and explanation
        """
        candidate = CandidateItem(
            country=candidate_country,
            denomination=candidate_denomination,
            year=candidate_year,
            grade=candidate_grade,
        )
        intelligence = FocusedCollectionIntelligenceEngine(self.collection_items)
        intelligence_result = intelligence.analyze_candidate(candidate)
        matching_items = intelligence.find_exact_items(candidate)
        
        if not matching_items:
            # No matching coins - not an upgrade scenario
            return self._create_no_match_recommendation(
                candidate_country, candidate_denomination, candidate_year,
                candidate_grade, candidate_estimate
            )
        
        # Get best existing item
        best_existing = self._get_intelligence_best_item(intelligence_result, matching_items)
        
        # Calculate upgrade metrics
        grade_improvement = self._calculate_grade_improvement(
            candidate_grade, best_existing.grade
        )
        value_improvement = candidate_estimate - self._estimate_value(best_existing)
        
        # Calculate upgrade score
        upgrade_score = self._calculate_upgrade_score(
            candidate_country, candidate_denomination, candidate_year,
            grade_improvement, value_improvement
        )
        
        # Determine verdict
        verdict = self._determine_verdict(
            intelligence_result, grade_improvement, upgrade_score,
            candidate_grade, best_existing.grade
        )
        
        # Generate explanation
        explanation = self._generate_explanation(
            verdict, candidate_country, candidate_denomination, candidate_year,
            candidate_grade, candidate_estimate, best_existing, grade_improvement,
            value_improvement, upgrade_score
        )
        
        # Generate reason
        reason = self._generate_reason(
            verdict, candidate_country, candidate_denomination, candidate_year,
            grade_improvement
        )
        
        # Calculate melt values (supporting factor, won't break if fails)
        candidate_melt_value_cad = None
        existing_melt_value_cad = None
        melt_value_improvement = None
        spot_price_warning = None
        try:
            # Calculate candidate melt value
            candidate_melt_result = self.melt_engine.calculate_melt_value(
                country=candidate_country,
                denomination=candidate_denomination,
                year=candidate_year
            )
            candidate_melt_value_cad = candidate_melt_result.melt_value_cad
            spot_price_warning = candidate_melt_result.spot_price_warning
            
            # Calculate existing melt value
            existing_melt_result = self.melt_engine.calculate_melt_value(
                country=best_existing.country,
                denomination=best_existing.denomination,
                year=best_existing.year
            )
            existing_melt_value_cad = existing_melt_result.melt_value_cad
            
            # Calculate melt value improvement
            if candidate_melt_value_cad is not None and existing_melt_value_cad is not None:
                melt_value_improvement = candidate_melt_value_cad - existing_melt_value_cad
            
            # Add melt value to explanation for silver coins
            if candidate_melt_value_cad > 0 or existing_melt_value_cad > 0:
                explanation += f"\n\n**Melt Value Analysis:**"
                if candidate_melt_value_cad > 0:
                    explanation += f"\n- Candidate melt value: ${candidate_melt_value_cad:.2f} CAD"
                if existing_melt_value_cad > 0:
                    explanation += f"\n- Existing melt value: ${existing_melt_value_cad:.2f} CAD"
                if melt_value_improvement is not None and melt_value_improvement != 0:
                    explanation += f"\n- Melt value difference: ${melt_value_improvement:.2f} CAD"
                if spot_price_warning:
                    explanation += f"\n- {spot_price_warning}"
        except Exception as e:
            # Melt value calculation failed, continue without it
            pass
        
        return UpgradeRecommendation(
            candidate_country=candidate_country,
            candidate_denomination=candidate_denomination,
            candidate_year=candidate_year,
            candidate_grade=candidate_grade,
            candidate_estimate=candidate_estimate,
            existing_country=best_existing.country,
            existing_denomination=best_existing.denomination,
            existing_year=best_existing.year,
            existing_grade=best_existing.grade,
            existing_estimate=self._estimate_value(best_existing),
            existing_item_id=best_existing.id,
            verdict=verdict,
            upgrade_score=upgrade_score,
            grade_improvement=grade_improvement,
            value_improvement=value_improvement,
            reason=reason,
            explanation=explanation,
            candidate_melt_value_cad=candidate_melt_value_cad,
            existing_melt_value_cad=existing_melt_value_cad,
            melt_value_improvement=melt_value_improvement,
            spot_price_warning=spot_price_warning
        )
    
    def _find_matching_items(
        self, country: str, denomination: str, year: str
    ) -> List:
        """Find owned items through the focused Collection Intelligence Engine."""
        candidate = CandidateItem(country=country, denomination=denomination, year=year)
        return FocusedCollectionIntelligenceEngine(self.collection_items).find_exact_items(candidate)

    def _get_intelligence_best_item(self, intelligence_result, matching_items: List):
        """Resolve the best item selected by Collection Intelligence."""
        best_match = intelligence_result.best_existing_match
        if best_match:
            for item in matching_items:
                if str(getattr(item, "id", "")) == best_match.item_id:
                    return item
        return self._get_best_grade_item(matching_items)
    
    def _get_best_grade_item(self, items: List):
        """Get item with highest grade from list."""
        graded = [item for item in items if self._grade_score(item.grade) > 0]
        if not graded:
            return items[0]  # Return first if none graded
        return sorted(graded, key=lambda item: self._grade_score(item.grade), reverse=True)[0]
    
    @staticmethod
    def _grade_score(grade: str) -> int:
        """Convert grade to numeric score."""
        return GRADE_HIERARCHY.get((grade or "").strip(), 0)
    
    @staticmethod
    def _estimate_value(item) -> float:
        """Estimate value from item."""
        try:
            return float(getattr(item, "estimate_cad", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    
    def _calculate_grade_improvement(self, candidate_grade: str, existing_grade: str) -> int:
        """Calculate grade improvement (positive = candidate is better)."""
        candidate_score = self._grade_score(candidate_grade)
        existing_score = self._grade_score(existing_grade)
        return candidate_score - existing_score
    
    def _calculate_upgrade_score(
        self, country: str, denomination: str, year: str,
        grade_improvement: int, value_improvement: float
    ) -> int:
        """Calculate overall upgrade score."""
        score = 0
        
        # Grade improvement (most important)
        if grade_improvement > 0:
            score += min(grade_improvement * 10, 50)  # Max 50 points for grade
        
        # Value improvement
        if value_improvement > 0:
            score += min(int(value_improvement / 10), 20)  # Max 20 points for value
        
        # Adam-specific priorities
        country_lower = country.lower()
        denom_lower = denomination.lower()
        
        if "newfoundland" in country_lower:
            score += 30
            if any(term in denom_lower for term in NEWFOUNDLAND_FOCUS_TERMS):
                score += 15
        
        if "canada" in country_lower and year == "1859" and ("cent" in denom_lower or "large" in denom_lower):
            score += 35
        
        if "canada" in country_lower and any(term in denom_lower for term in SILVER_DENOMINATION_TERMS):
            score += 25
        
        return min(score, 100)
    
    def _determine_verdict(
        self, intelligence_result, grade_improvement: int, upgrade_score: int,
        candidate_grade: str, existing_grade: str
    ) -> str:
        """Determine upgrade verdict from Collection Intelligence status and legacy score."""
        if intelligence_result.match_status.value != "BETTER_GRADE_UPGRADE":
            return "Hold Existing"
        
        if upgrade_score >= 70:
            return "Strong Upgrade"
        
        if upgrade_score >= 40:
            return "Upgrade"
        
        return "Hold Existing"
    
    def _generate_explanation(
        self, verdict: str, candidate_country: str, candidate_denomination: str,
        candidate_year: str, candidate_grade: str, candidate_estimate: float,
        existing_item, grade_improvement: int, value_improvement: float,
        upgrade_score: int
    ) -> str:
        """Generate human-readable explanation."""
        lines = [
            f"Upgrade Analysis for {candidate_country} {candidate_denomination} {candidate_year}",
            "",
            f"**Candidate Coin:**",
            f"- Grade: {candidate_grade or 'Ungraded'}",
            f"- Estimated Value: ${candidate_estimate:.2f}" if candidate_estimate > 0 else "- Estimated Value: Not available",
            "",
            f"**Existing Coin:**",
            f"- Grade: {existing_item.grade or 'Ungraded'}",
            f"- Estimated Value: ${self._estimate_value(existing_item):.2f}" if self._estimate_value(existing_item) > 0 else "- Estimated Value: Not available",
            f"- Item ID: {existing_item.id}",
            "",
        ]
        
        if grade_improvement > 0:
            lines.append(f"**Grade Improvement:** +{grade_improvement} grade levels")
        elif grade_improvement < 0:
            lines.append(f"**Grade Difference:** {grade_improvement} grade levels (candidate is lower)")
        else:
            lines.append("**Grade Difference:** No grade difference")
        
        if value_improvement > 0:
            lines.append(f"**Value Improvement:** +${value_improvement:.2f}")
        elif value_improvement < 0:
            lines.append(f"**Value Difference:** ${value_improvement:.2f} (candidate is lower)")
        
        lines.extend([
            "",
            f"**Upgrade Score:** {upgrade_score}/100",
            f"**Verdict:** {verdict}",
            "",
            self._get_verdict_explanation(verdict, candidate_country, candidate_denomination),
        ])
        
        return "\n".join(lines)
    
    def _get_verdict_explanation(self, verdict: str, country: str, denomination: str) -> str:
        """Get verdict-specific explanation."""
        country_lower = country.lower()
        denom_lower = denomination.lower()
        
        if verdict == "Strong Upgrade":
            reasons = ["This is a significant upgrade opportunity."]
            if "newfoundland" in country_lower:
                reasons.append("Newfoundland coins are a high priority for your collection.")
            if "canada" in country_lower and any(term in denom_lower for term in SILVER_DENOMINATION_TERMS):
                reasons.append("Canadian silver coins are a priority for your collection.")
            return " ".join(reasons)
        
        if verdict == "Upgrade":
            return "This represents a moderate upgrade opportunity. Consider the grade improvement and value impact before deciding."
        
        if verdict == "Hold Existing":
            return "The candidate coin does not represent a significant upgrade over your existing holding. Keep your current coin."
        
        return "Unable to determine upgrade potential."
    
    def _generate_reason(
        self, verdict: str, country: str, denomination: str, year: str,
        grade_improvement: int
    ) -> str:
        """Generate concise reason for verdict."""
        if verdict == "Strong Upgrade":
            return f"Strong upgrade: +{grade_improvement} grade levels with high priority factors."
        if verdict == "Upgrade":
            return f"Moderate upgrade: +{grade_improvement} grade levels."
        if verdict == "Hold Existing":
            return "Candidate does not improve upon existing holding."
        return "No upgrade recommendation."
    
    def _create_no_match_recommendation(
        self, country: str, denomination: str, year: str,
        grade: str, estimate: float
    ) -> UpgradeRecommendation:
        """Create recommendation when no matching coins exist."""
        return UpgradeRecommendation(
            candidate_country=country,
            candidate_denomination=denomination,
            candidate_year=year,
            candidate_grade=grade,
            candidate_estimate=estimate,
            existing_country="",
            existing_denomination="",
            existing_year="",
            existing_grade="",
            existing_estimate=0.0,
            existing_item_id="",
            verdict="Pass",
            upgrade_score=0,
            grade_improvement=0,
            value_improvement=0.0,
            reason="No matching coin in collection.",
            explanation=f"No matching coin found in collection for {country} {denomination} {year}. This is not an upgrade scenario.",
            candidate_melt_value_cad=None,
            existing_melt_value_cad=None,
            melt_value_improvement=None,
            spot_price_warning=None
        )
    
    def export_to_csv(self, recommendations: List[UpgradeRecommendation], output_path: str) -> bool:
        """Export upgrade recommendations to CSV."""
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    "candidate_country", "candidate_denomination", "candidate_year",
                    "candidate_grade", "candidate_estimate",
                    "existing_country", "existing_denomination", "existing_year",
                    "existing_grade", "existing_estimate", "existing_item_id",
                    "verdict", "upgrade_score", "grade_improvement",
                    "value_improvement", "reason", "explanation",
                    "candidate_melt_value_cad", "existing_melt_value_cad",
                    "melt_value_improvement", "spot_price_warning"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for rec in recommendations:
                    writer.writerow(rec.to_dict())
            return True
        except Exception as e:
            print(f"Error exporting to CSV: {e}")
            return False
