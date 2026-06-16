"""Portfolio Dashboard for high-level collection health overview."""

import csv
from dataclasses import dataclass
from typing import Dict, List, Optional
from collection_intelligence import CollectionIntelligenceEngine, SILVER_DENOMINATION_TERMS, NEWFOUNDLAND_FOCUS_TERMS
from melt_value_engine import MeltValueEngine, ASWReferenceLoader, ManualSpotPriceProvider


@dataclass
class DashboardSummary:
    """High-level dashboard summary."""
    total_items: int
    total_countries: int
    total_estimated_value_cad: float
    total_melt_value_cad: float
    newfoundland_progress: Dict
    canadian_silver_progress: Dict
    large_cent_1859_progress: Dict
    top_gap_targets: List[Dict]
    top_upgrade_targets: List[Dict]
    duplicate_heavy_areas: List[Dict]
    want_list_progress: Dict


class PortfolioDashboard:
    """Portfolio dashboard for collection health overview."""
    
    def __init__(self, items: List, staged_want_list_intents: Optional[List] = None):
        """
        Initialize portfolio dashboard.
        
        Args:
            items: Collection items
            staged_want_list_intents: Optional staged WANT_LIST intents
        """
        self.items = items
        self.staged_want_list_intents = staged_want_list_intents or []
        
        # Initialize engines
        self.intelligence = CollectionIntelligenceEngine(items)
        self.asw_loader = ASWReferenceLoader()
        self.spot_provider = ManualSpotPriceProvider(default_spot_price_cad=35.0)
        self.melt_engine = MeltValueEngine(self.asw_loader, self.spot_provider)
    
    def generate_dashboard(self) -> DashboardSummary:
        """
        Generate comprehensive dashboard summary.
        
        Returns:
            DashboardSummary with all metrics
        """
        # Basic totals
        total_items = len(self.items)
        total_countries = len(self.intelligence.analyze_by_country())
        
        # Value calculations
        total_estimated_value_cad = self._calculate_total_estimated_value()
        total_melt_value_cad = self._calculate_total_melt_value()
        
        # Priority progress
        newfoundland_progress = self._calculate_newfoundland_progress()
        canadian_silver_progress = self._calculate_canadian_silver_progress()
        large_cent_1859_progress = self._calculate_large_cent_1859_progress()
        
        # Targets and duplicates
        top_gap_targets = self._get_top_gap_targets(limit=5)
        top_upgrade_targets = self._get_top_upgrade_targets(limit=5)
        duplicate_heavy_areas = self._get_duplicate_heavy_areas(limit=5)
        
        # WANT_LIST progress
        want_list_progress = self._calculate_want_list_progress()
        
        return DashboardSummary(
            total_items=total_items,
            total_countries=total_countries,
            total_estimated_value_cad=total_estimated_value_cad,
            total_melt_value_cad=total_melt_value_cad,
            newfoundland_progress=newfoundland_progress,
            canadian_silver_progress=canadian_silver_progress,
            large_cent_1859_progress=large_cent_1859_progress,
            top_gap_targets=top_gap_targets,
            top_upgrade_targets=top_upgrade_targets,
            duplicate_heavy_areas=duplicate_heavy_areas,
            want_list_progress=want_list_progress,
        )
    
    def _calculate_total_estimated_value(self) -> float:
        """Calculate total estimated value from collection."""
        total = 0.0
        for item in self.items:
            estimate = getattr(item, 'estimate_cad', None)
            if estimate:
                try:
                    total += float(estimate) * max(int(getattr(item, 'quantity', 1) or 1), 1)
                except (ValueError, TypeError):
                    continue
        return total
    
    def _calculate_total_melt_value(self) -> float:
        """Calculate total melt value from silver coins."""
        total = 0.0
        for item in self.items:
            result = self.melt_engine.calculate_melt_value(
                country=item.country or "",
                denomination=item.denomination or "",
                year=item.year or ""
            )
            if result.is_silver:
                quantity = max(int(getattr(item, 'quantity', 1) or 1), 1)
                total += result.melt_value_cad * quantity
        return total
    
    def _calculate_newfoundland_progress(self) -> Dict:
        """Calculate Newfoundland coinage progress."""
        newfoundland_items = [
            item for item in self.items
            if item.country == "Newfoundland"
        ]
        
        series = {}
        for item in newfoundland_items:
            denom = item.denomination or "Unknown"
            if denom not in series:
                series[denom] = {"count": 0, "years": set()}
            series[denom]["count"] += max(int(getattr(item, 'quantity', 1) or 1), 1)
            if item.year:
                series[denom]["years"].add(item.year)
        
        return {
            "total_items": len(newfoundland_items),
            "denominations": len(series),
            "series": {k: {"count": v["count"], "years": len(v["years"])} for k, v in series.items()}
        }
    
    def _calculate_canadian_silver_progress(self) -> Dict:
        """Calculate Canadian silver coinage progress."""
        canadian_silver_items = [
            item for item in self.items
            if item.country == "Canada" and self._is_silver_denomination(item.denomination)
        ]
        
        series = {}
        for item in canadian_silver_items:
            denom = item.denomination or "Unknown"
            if denom not in series:
                series[denom] = {"count": 0, "years": set()}
            series[denom]["count"] += max(int(getattr(item, 'quantity', 1) or 1), 1)
            if item.year:
                series[denom]["years"].add(item.year)
        
        return {
            "total_items": len(canadian_silver_items),
            "denominations": len(series),
            "series": {k: {"count": v["count"], "years": len(v["years"])} for k, v in series.items()}
        }
    
    def _calculate_large_cent_1859_progress(self) -> Dict:
        """Calculate 1859 Large Cent progress."""
        large_cent_items = [
            item for item in self.items
            if item.country == "Canada" and item.denomination == "1 cent" and item.year == "1859"
        ]
        
        grades = {}
        for item in large_cent_items:
            grade = item.grade or "Unknown"
            grades[grade] = grades.get(grade, 0) + max(int(getattr(item, 'quantity', 1) or 1), 1)
        
        return {
            "total_items": len(large_cent_items),
            "grades": grades,
            "unique_grades": len(grades)
        }
    
    def _get_top_gap_targets(self, limit: int = 5) -> List[Dict]:
        """Get top gap-fill targets."""
        priorities = self.intelligence.generate_acquisition_priorities(
            limit=limit,
            staged_want_list_intents=self.staged_want_list_intents
        )
        return [target.to_dict() for target in priorities[:limit]]
    
    def _get_top_upgrade_targets(self, limit: int = 5) -> List[Dict]:
        """Get top upgrade targets."""
        candidates = self.intelligence.detect_upgrade_candidates()
        return [
            {
                "country": c["country"],
                "denomination": c["denomination"],
                "year": c["year"],
                "current_best_grade": c["current_best_grade"],
                "reason": c["reason"]
            }
            for c in candidates[:limit]
        ]
    
    def _get_duplicate_heavy_areas(self, limit: int = 5) -> List[Dict]:
        """Get areas with heavy duplicates."""
        duplicates = self.intelligence.detect_duplicates()
        return [
            {
                "country": d["country"],
                "denomination": d["denomination"],
                "year": d["year"],
                "count": d["count"]
            }
            for d in duplicates[:limit]
        ]
    
    def _calculate_want_list_progress(self) -> Dict:
        """Calculate WANT_LIST progress."""
        if not self.staged_want_list_intents:
            return {
                "total_intents": 0,
                "fulfilled": 0,
                "pending": 0,
                "progress_percentage": 0.0
            }
        
        total = len(self.staged_want_list_intents)
        fulfilled = 0
        
        for intent in self.staged_want_list_intents:
            intent_country = getattr(intent, 'country', '')
            intent_denom = getattr(intent, 'denomination', '')
            intent_year = getattr(intent, 'year', '')
            
            # Check if we have this coin in collection
            for item in self.items:
                if (item.country == intent_country and 
                    item.denomination == intent_denom and 
                    item.year == intent_year):
                    fulfilled += 1
                    break
        
        return {
            "total_intents": total,
            "fulfilled": fulfilled,
            "pending": total - fulfilled,
            "progress_percentage": (fulfilled / total * 100) if total > 0 else 0.0
        }
    
    def _is_silver_denomination(self, denomination: Optional[str]) -> bool:
        """Check if denomination is silver."""
        if not denomination:
            return False
        denom_lower = denomination.lower()
        return any(term in denom_lower for term in SILVER_DENOMINATION_TERMS)
    
    def export_to_csv(self, filepath: str) -> None:
        """
        Export dashboard to CSV.
        
        Args:
            filepath: Output CSV file path
        """
        dashboard = self.generate_dashboard()
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Summary section
            writer.writerow(["Portfolio Dashboard Summary"])
            writer.writerow([])
            writer.writerow(["Total Items", dashboard.total_items])
            writer.writerow(["Total Countries", dashboard.total_countries])
            writer.writerow(["Total Estimated Value (CAD)", f"{dashboard.total_estimated_value_cad:.2f}"])
            writer.writerow(["Total Melt Value (CAD)", f"{dashboard.total_melt_value_cad:.2f}"])
            writer.writerow([])
            
            # Newfoundland progress
            writer.writerow(["Newfoundland Progress"])
            writer.writerow(["Total Items", dashboard.newfoundland_progress["total_items"]])
            writer.writerow(["Denominations", dashboard.newfoundland_progress["denominations"]])
            for denom, data in dashboard.newfoundland_progress["series"].items():
                writer.writerow([denom, data["count"], data["years"]])
            writer.writerow([])
            
            # Canadian silver progress
            writer.writerow(["Canadian Silver Progress"])
            writer.writerow(["Total Items", dashboard.canadian_silver_progress["total_items"]])
            writer.writerow(["Denominations", dashboard.canadian_silver_progress["denominations"]])
            for denom, data in dashboard.canadian_silver_progress["series"].items():
                writer.writerow([denom, data["count"], data["years"]])
            writer.writerow([])
            
            # 1859 Large Cent progress
            writer.writerow(["1859 Large Cent Progress"])
            writer.writerow(["Total Items", dashboard.large_cent_1859_progress["total_items"]])
            writer.writerow(["Unique Grades", dashboard.large_cent_1859_progress["unique_grades"]])
            for grade, count in dashboard.large_cent_1859_progress["grades"].items():
                writer.writerow([grade, count])
            writer.writerow([])
            
            # Top gap targets
            writer.writerow(["Top Gap-Fill Targets"])
            writer.writerow(["Country", "Denomination", "Year", "Type", "Priority", "Reason"])
            for target in dashboard.top_gap_targets:
                writer.writerow([
                    target["country"],
                    target["denomination"],
                    target["year"],
                    target["target_type"],
                    target["priority_score"],
                    target["reason"]
                ])
            writer.writerow([])
            
            # Top upgrade targets
            writer.writerow(["Top Upgrade Targets"])
            writer.writerow(["Country", "Denomination", "Year", "Best Grade", "Reason"])
            for target in dashboard.top_upgrade_targets:
                writer.writerow([
                    target["country"],
                    target["denomination"],
                    target["year"],
                    target["current_best_grade"],
                    target["reason"]
                ])
            writer.writerow([])
            
            # Duplicate-heavy areas
            writer.writerow(["Duplicate-Heavy Areas"])
            writer.writerow(["Country", "Denomination", "Year", "Count"])
            for dup in dashboard.duplicate_heavy_areas:
                writer.writerow([
                    dup["country"],
                    dup["denomination"],
                    dup["year"],
                    dup["count"]
                ])
            writer.writerow([])
            
            # WANT_LIST progress
            writer.writerow(["WANT_LIST Progress"])
            writer.writerow(["Total Intents", dashboard.want_list_progress["total_intents"]])
            writer.writerow(["Fulfilled", dashboard.want_list_progress["fulfilled"]])
            writer.writerow(["Pending", dashboard.want_list_progress["pending"]])
            writer.writerow(["Progress Percentage", f"{dashboard.want_list_progress['progress_percentage']:.1f}%"])
    
    def export_to_markdown(self, filepath: str) -> None:
        """
        Export dashboard to Markdown.
        
        Args:
            filepath: Output Markdown file path
        """
        dashboard = self.generate_dashboard()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# Portfolio Dashboard Summary\n\n")
            
            # Summary section
            f.write("## Collection Overview\n\n")
            f.write(f"- **Total Items:** {dashboard.total_items}\n")
            f.write(f"- **Total Countries:** {dashboard.total_countries}\n")
            f.write(f"- **Total Estimated Value:** CAD ${dashboard.total_estimated_value_cad:.2f}\n")
            f.write(f"- **Total Melt Value:** CAD ${dashboard.total_melt_value_cad:.2f}\n\n")
            
            # Newfoundland progress
            f.write("## Newfoundland Coinage Progress\n\n")
            f.write(f"- **Total Items:** {dashboard.newfoundland_progress['total_items']}\n")
            f.write(f"- **Denominations:** {dashboard.newfoundland_progress['denominations']}\n\n")
            f.write("### By Denomination\n\n")
            f.write("| Denomination | Count | Years |\n")
            f.write("|--------------|-------|-------|\n")
            for denom, data in dashboard.newfoundland_progress["series"].items():
                f.write(f"| {denom} | {data['count']} | {data['years']} |\n")
            f.write("\n")
            
            # Canadian silver progress
            f.write("## Canadian Silver Coinage Progress\n\n")
            f.write(f"- **Total Items:** {dashboard.canadian_silver_progress['total_items']}\n")
            f.write(f"- **Denominations:** {dashboard.canadian_silver_progress['denominations']}\n\n")
            f.write("### By Denomination\n\n")
            f.write("| Denomination | Count | Years |\n")
            f.write("|--------------|-------|-------|\n")
            for denom, data in dashboard.canadian_silver_progress["series"].items():
                f.write(f"| {denom} | {data['count']} | {data['years']} |\n")
            f.write("\n")
            
            # 1859 Large Cent progress
            f.write("## 1859 Large Cent Progress\n\n")
            f.write(f"- **Total Items:** {dashboard.large_cent_1859_progress['total_items']}\n")
            f.write(f"- **Unique Grades:** {dashboard.large_cent_1859_progress['unique_grades']}\n\n")
            f.write("### By Grade\n\n")
            f.write("| Grade | Count |\n")
            f.write("|-------|-------|\n")
            for grade, count in dashboard.large_cent_1859_progress["grades"].items():
                f.write(f"| {grade} | {count} |\n")
            f.write("\n")
            
            # Top gap targets
            f.write("## Top Gap-Fill Targets\n\n")
            f.write("| Country | Denomination | Year | Type | Priority | Reason |\n")
            f.write("|---------|--------------|------|------|----------|--------|\n")
            for target in dashboard.top_gap_targets:
                f.write(f"| {target['country']} | {target['denomination']} | {target['year']} | {target['target_type']} | {target['priority_score']} | {target['reason']} |\n")
            f.write("\n")
            
            # Top upgrade targets
            f.write("## Top Upgrade Targets\n\n")
            f.write("| Country | Denomination | Year | Best Grade | Reason |\n")
            f.write("|---------|--------------|------|-------------|--------|\n")
            for target in dashboard.top_upgrade_targets:
                f.write(f"| {target['country']} | {target['denomination']} | {target['year']} | {target['current_best_grade']} | {target['reason']} |\n")
            f.write("\n")
            
            # Duplicate-heavy areas
            f.write("## Duplicate-Heavy Areas\n\n")
            f.write("| Country | Denomination | Year | Count |\n")
            f.write("|---------|--------------|------|-------|\n")
            for dup in dashboard.duplicate_heavy_areas:
                f.write(f"| {dup['country']} | {dup['denomination']} | {dup['year']} | {dup['count']} |\n")
            f.write("\n")
            
            # WANT_LIST progress
            f.write("## WANT_LIST Progress\n\n")
            f.write(f"- **Total Intents:** {dashboard.want_list_progress['total_intents']}\n")
            f.write(f"- **Fulfilled:** {dashboard.want_list_progress['fulfilled']}\n")
            f.write(f"- **Pending:** {dashboard.want_list_progress['pending']}\n")
            f.write(f"- **Progress:** {dashboard.want_list_progress['progress_percentage']:.1f}%\n")
