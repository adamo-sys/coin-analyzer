"""
Numista Intelligence Engine
Deterministic, offline analysis of Numista export data for collection intelligence.

Provides gap analysis, duplicate detection, upgrade opportunities, variety detection,
and acquisition priority scoring without live API calls, web scraping, or external services.

v7.5 milestone: Numista Intelligence
"""

import os
import json
import pandas as pd
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
from enum import Enum

from coin_collection import CoinItem, CoinCollection
from collection_intelligence import CollectionIntelligenceEngine


class NumistaMatchStatus(Enum):
    """Status of a Numista item relative to local collection."""
    OWNED = "owned"
    DUPLICATE = "duplicate"
    UPGRADE = "upgrade"
    GAP = "gap"
    VARIETY = "variety"
    NEW_SERIES = "new_series"
    NOT_RELEVANT = "not_relevant"


class NumistaPriority(Enum):
    """Acquisition priority for Numista opportunities."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class NumistaItemAnalysis:
    """Analysis result for a single Numista item."""
    numista_n: str
    title: str
    country: str
    denomination: str
    year: str
    grade: str
    reference: str
    issuer: str
    currency: str
    face_value: str
    estimate_cad: float
    status: NumistaMatchStatus
    priority: NumistaPriority
    matched_collection_item: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    series_relevance: Optional[str] = None
    gap_value: float = 0.0
    upgrade_delta: float = 0.0
    comment: str = ""
    notes: str = ""


@dataclass
class NumistaGapReport:
    """Gap analysis report from Numista perspective."""
    series_name: str
    owned_dates: List[str]
    missing_dates: List[str]
    completion_pct: float
    want_list_count: int
    numista_items_available: int
    priority: NumistaPriority
    recommendations: List[str] = field(default_factory=list)


@dataclass
class NumistaDuplicateReport:
    """Duplicate detection report."""
    numista_item: NumistaItemAnalysis
    collection_item_id: str
    collection_item_title: str
    duplicate_reason: str
    recommendation: str


@dataclass
class NumistaUpgradeReport:
    """Upgrade opportunity report."""
    numista_item: NumistaItemAnalysis
    existing_item_id: str
    existing_item_title: str
    existing_grade: str
    proposed_grade: str
    upgrade_reason: str
    priority: NumistaPriority


@dataclass
class NumistaIntelligenceReport:
    """Complete Numista Intelligence report."""
    report_date: str
    total_numista_items: int
    analyzed_items: int
    owned_count: int
    duplicate_count: int
    upgrade_count: int
    gap_count: int
    variety_count: int
    new_series_count: int
    not_relevant_count: int
    gap_reports: List[NumistaGapReport] = field(default_factory=list)
    duplicate_reports: List[NumistaDuplicateReport] = field(default_factory=list)
    upgrade_reports: List[NumistaUpgradeReport] = field(default_factory=list)
    item_analyses: List[NumistaItemAnalysis] = field(default_factory=list)
    top_priorities: List[NumistaItemAnalysis] = field(default_factory=list)
    series_opportunities: List[NumistaGapReport] = field(default_factory=list)
    summary_recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'report_date': self.report_date,
            'total_numista_items': self.total_numista_items,
            'analyzed_items': self.analyzed_items,
            'owned_count': self.owned_count,
            'duplicate_count': self.duplicate_count,
            'upgrade_count': self.upgrade_count,
            'gap_count': self.gap_count,
            'variety_count': self.variety_count,
            'new_series_count': self.new_series_count,
            'not_relevant_count': self.not_relevant_count,
            'gap_reports': [asdict(r) for r in self.gap_reports],
            'duplicate_reports': [asdict(r) for r in self.duplicate_reports],
            'upgrade_reports': [asdict(r) for r in self.upgrade_reports],
            'item_analyses': [asdict(a) for a in self.item_analyses],
            'top_priorities': [asdict(a) for a in self.top_priorities],
            'series_opportunities': [asdict(r) for r in self.series_opportunities],
            'summary_recommendations': self.summary_recommendations,
            'warnings': self.warnings,
        }


class NumistaDataModel:
    """Parse and normalize Numista export data."""

    EXPECTED_COLUMNS = [
        'N# number (with link)', 'Title', 'Country', 'Issuer',
        'Face value', 'Currency', 'Year', 'Grade', 'Reference',
        'Comment', 'Private comment', 'Quantity', 'Estimate (CAD)'
    ]

    def __init__(self):
        self.raw_data: Optional[pd.DataFrame] = None
        self.normalized_items: List[Dict] = []
        self.parse_errors: List[str] = []

    def load_from_excel(self, file_path: str) -> bool:
        try:
            self.raw_data = pd.read_excel(file_path)
            self._normalize_data()
            return True
        except Exception as e:
            self.parse_errors.append(f"Excel load error: {str(e)}")
            return False

    def load_from_csv(self, file_path: str) -> bool:
        try:
            self.raw_data = pd.read_csv(file_path)
            self._normalize_data()
            return True
        except Exception as e:
            self.parse_errors.append(f"CSV load error: {str(e)}")
            return False

    def _normalize_data(self):
        self.normalized_items = []
        if self.raw_data is None:
            return
        for _, row in self.raw_data.iterrows():
            item = self._normalize_row(row)
            if item:
                self.normalized_items.append(item)

    def _normalize_row(self, row: pd.Series) -> Optional[Dict]:
        try:
            numista_n = self._extract_numista_n(row.get('N# number (with link)', ''))
            year_value = self._format_year(row.get('Year', ''))
            return {
                'numista_n': numista_n,
                'title': self._clean_value(row.get('Title', '')),
                'country': self._clean_value(row.get('Country', '')),
                'issuer': self._clean_value(row.get('Issuer', '')),
                'face_value': self._clean_value(row.get('Face value', '')),
                'currency': self._clean_value(row.get('Currency', '')),
                'year': year_value,
                'grade': self._clean_value(row.get('Grade', '')),
                'reference': self._clean_value(row.get('Reference', '')),
                'comment': self._clean_value(row.get('Comment', '')),
                'private_comment': self._clean_value(row.get('Private comment', '')),
                'quantity': int(row.get('Quantity', 1)) if pd.notna(row.get('Quantity')) else 1,
                'estimate_cad': float(row.get('Estimate (CAD)', 0)) if pd.notna(row.get('Estimate (CAD)')) else 0.0,
            }
        except Exception as e:
            self.parse_errors.append(f"Row normalization error: {str(e)}")
            return None

    def _clean_value(self, value) -> str:
        if pd.isna(value):
            return ''
        return str(value).strip()

    def _format_year(self, year_value) -> str:
        if pd.isna(year_value):
            return ''
        if isinstance(year_value, float) and year_value.is_integer():
            return str(int(year_value))
        return str(year_value).strip()

    def _extract_numista_n(self, n_link: str) -> str:
        if pd.isna(n_link) or not n_link:
            return ""
        s = str(n_link).strip()
        if "N#" in s:
            return s.split("N#")[-1].strip()
        # Handle URLs like https://numista.com/catalogue/pieces12345
        import re as _re
        m = _re.search(r'pieces(\d+)', s)
        if m:
            return m.group(1)
        return s

    def get_items(self) -> List[Dict]:
        return self.normalized_items

    def get_validation_summary(self) -> Dict:
        return {
            'total_rows': len(self.raw_data) if self.raw_data is not None else 0,
            'normalized_items': len(self.normalized_items),
            'parse_errors': len(self.parse_errors),
            'errors': self.parse_errors[:10],
        }


class NumistaCollectionAnalyzer:
    """Compare Numista data against local collection."""

    def __init__(self, collection: CoinCollection):
        self.collection = collection
        self.intelligence_engine = CollectionIntelligenceEngine(collection.items)

    def analyze_item(self, numista_item: Dict) -> NumistaItemAnalysis:
        analysis = NumistaItemAnalysis(
            numista_n=numista_item.get('numista_n', ''),
            title=numista_item.get('title', ''),
            country=numista_item.get('country', ''),
            denomination=numista_item.get('face_value', ''),
            year=numista_item.get('year', ''),
            grade=numista_item.get('grade', ''),
            reference=numista_item.get('reference', ''),
            issuer=numista_item.get('issuer', ''),
            currency=numista_item.get('currency', ''),
            face_value=numista_item.get('face_value', ''),
            estimate_cad=numista_item.get('estimate_cad', 0.0),
            status=NumistaMatchStatus.NOT_RELEVANT,
            priority=NumistaPriority.NONE,
            reasons=[],
            warnings=[],
        )

        owned_item = self._find_by_numista_n(analysis.numista_n)
        if owned_item:
            analysis.status = NumistaMatchStatus.OWNED
            analysis.matched_collection_item = owned_item.id
            analysis.priority = NumistaPriority.NONE
            analysis.reasons.append(f"Already owned (N# {analysis.numista_n})")
            return analysis

        owned_item = self._find_by_signature(analysis.country, analysis.year, analysis.reference)
        if owned_item:
            if self._is_upgrade(owned_item, analysis):
                analysis.status = NumistaMatchStatus.UPGRADE
                analysis.matched_collection_item = owned_item.id
                analysis.priority = NumistaPriority.HIGH
                analysis.upgrade_delta = self._calculate_upgrade_delta(owned_item, analysis)
                analysis.reasons.append(f"Upgrade opportunity: owned grade {owned_item.grade}, Numista grade {analysis.grade}")
            else:
                analysis.status = NumistaMatchStatus.DUPLICATE
                analysis.matched_collection_item = owned_item.id
                analysis.priority = NumistaPriority.NONE
                analysis.reasons.append(f"Duplicate: already owned ({owned_item.id})")
            return analysis

        series_relevance = self._check_series_relevance(analysis)
        if series_relevance:
            analysis.series_relevance = series_relevance
            analysis.status = NumistaMatchStatus.GAP
            analysis.priority = self._calculate_gap_priority(analysis)
            analysis.gap_value = self._calculate_gap_value(analysis)
            analysis.reasons.append(f"Collection gap in {series_relevance}")
        else:
            if self._is_newfoundland(analysis) or self._is_canadian_silver(analysis):
                analysis.status = NumistaMatchStatus.NEW_SERIES
                analysis.priority = NumistaPriority.MEDIUM
                analysis.reasons.append("New series opportunity for Adam-specific priorities")
            else:
                analysis.status = NumistaMatchStatus.NOT_RELEVANT
                analysis.priority = NumistaPriority.NONE
                analysis.reasons.append("Not in supported collecting areas")

        if self._has_variety_indicators(analysis):
            if analysis.status in [NumistaMatchStatus.GAP, NumistaMatchStatus.NEW_SERIES]:
                analysis.status = NumistaMatchStatus.VARIETY
                analysis.priority = NumistaPriority.HIGH
                analysis.reasons.append("Variety opportunity")

        return analysis

    def _find_by_numista_n(self, numista_n: str) -> Optional[CoinItem]:
        if not numista_n:
            return None
        for item in self.collection.items:
            if item.numista_n == numista_n:
                return item
        return None

    def _find_by_signature(self, country: str, year: str, reference: str) -> Optional[CoinItem]:
        if not country or not year:
            return None
        for item in self.collection.items:
            if (item.country == country and 
                item.year == year and 
                (item.reference == reference or not reference)):
                return item
        return None

    def _is_upgrade(self, existing: CoinItem, numista: NumistaItemAnalysis) -> bool:
        if not existing.grade or not numista.grade:
            return False
        grade_order = ['AG', 'G', 'VG', 'F', 'VF', 'EF', 'AU', 'UNC', 'BU', 'Proof', 'MS60', 'MS61',
                       'MS62', 'MS63', 'MS64', 'MS65', 'MS66', 'MS67', 'MS68', 'MS69', 'MS70']
        existing_idx = -1
        numista_idx = -1
        for i, g in enumerate(grade_order):
            if g in existing.grade.upper():
                existing_idx = i
            if g in numista.grade.upper():
                numista_idx = i
        if existing_idx >= 0 and numista_idx >= 0:
            return numista_idx > existing_idx
        return len(numista.grade) > len(existing.grade)

    def _calculate_upgrade_delta(self, existing: CoinItem, numista: NumistaItemAnalysis) -> float:
        if numista.estimate_cad > 0 and existing.estimate_cad > 0:
            return numista.estimate_cad - existing.estimate_cad
        return 0.0

    def _check_series_relevance(self, analysis: NumistaItemAnalysis) -> Optional[str]:
        supported_series = [
            'Newfoundland 5 Cents', 'Newfoundland 10 Cents', 'Newfoundland 20 Cents',
            'Newfoundland 50 Cents', 'Newfoundland 1 Cent',
            'Canadian Large Cents', 'Canadian Small Cents', 'Canadian Silver Dollars'
        ]
        for series in supported_series:
            if self._matches_series(analysis, series):
                return series
        return None

    def _matches_series(self, analysis: NumistaItemAnalysis, series: str) -> bool:
        country = analysis.country.lower()
        denomination = analysis.denomination.lower()
        if 'newfoundland' in series.lower():
            if 'newfoundland' in country or 'newfoundland' in analysis.issuer.lower():
                if '5 cent' in series.lower() and ('5' in denomination or 'five' in denomination):
                    return True
                if '10 cent' in series.lower() and ('10' in denomination or 'ten' in denomination or 'dime' in denomination):
                    return True
                if '20 cent' in series.lower() and ('20' in denomination or 'twenty' in denomination):
                    return True
                if '50 cent' in series.lower() and ('50' in denomination or 'half' in denomination):
                    return True
                if '1 cent' in series.lower() and ('1' in denomination or 'cent' in denomination or 'penny' in denomination):
                    return True
        if 'canadian' in series.lower():
            if 'canada' in country or 'canadian' in country:
                if 'large cent' in series.lower() and ('cent' in denomination and ('large' in analysis.title.lower() or 'large' in analysis.notes.lower())):
                    return True
                if 'small cent' in series.lower() and ('cent' in denomination and 'small' in analysis.title.lower()):
                    return True
                if 'silver dollar' in series.lower() and ('dollar' in denomination or '$1' in denomination):
                    return True
        return False

    def _calculate_gap_priority(self, analysis: NumistaItemAnalysis) -> NumistaPriority:
        if self._is_newfoundland(analysis):
            return NumistaPriority.HIGH
        if self._is_canadian_silver(analysis):
            return NumistaPriority.MEDIUM
        if self._is_key_date(analysis):
            return NumistaPriority.HIGH
        return NumistaPriority.MEDIUM

    def _calculate_gap_value(self, analysis: NumistaItemAnalysis) -> float:
        value = 0.0
        if self._is_newfoundland(analysis):
            value += 50.0
        if self._is_key_date(analysis):
            value += 30.0
        if analysis.estimate_cad > 0:
            value += min(analysis.estimate_cad * 0.1, 20.0)
        return value

    def _is_newfoundland(self, analysis: NumistaItemAnalysis) -> bool:
        return ('newfoundland' in analysis.country.lower() or 
                'newfoundland' in analysis.issuer.lower())

    def _is_canadian_silver(self, analysis: NumistaItemAnalysis) -> bool:
        if 'canada' not in analysis.country.lower() and 'canadian' not in analysis.country.lower():
            return False
        silver_indicators = ['silver', 'dime', 'quarter', 'half', '50 cent', '25 cent', '10 cent', '20 cent']
        return any(ind in analysis.denomination.lower() or ind in analysis.title.lower() for ind in silver_indicators)

    def _is_key_date(self, analysis: NumistaItemAnalysis) -> bool:
        key_dates = {
            'newfoundland': ['1880', '1885', '1888', '1917', '1919', '1921', '1929'],
            'canada': ['1859', '1921', '1925', '1926', '1947', '1948', '1951'],
        }
        year = analysis.year
        for country, dates in key_dates.items():
            if country in analysis.country.lower() and year in dates:
                return True
        return False

    def _has_variety_indicators(self, analysis: NumistaItemAnalysis) -> bool:
        variety_terms = ['variety', 'narrow', 'wide', '8 over', '9 over', 'repunched',
                         'double', 'large bust', 'small bust', 'near', 'far', 'dot']
        text = f"{analysis.title} {analysis.reference} {analysis.comment}".lower()
        return any(term in text for term in variety_terms)


class NumistaIntelligenceEngine:
    """Orchestrates Numista data loading, analysis, and report generation."""

    def __init__(self, collection: CoinCollection):
        self.collection = collection
        self.data_model = NumistaDataModel()
        self.analyzer = NumistaCollectionAnalyzer(collection)
        self.report: Optional[NumistaIntelligenceReport] = None

    def analyze_file(self, file_path: str) -> NumistaIntelligenceReport:
        if file_path.endswith('.csv'):
            success = self.data_model.load_from_csv(file_path)
        else:
            success = self.data_model.load_from_excel(file_path)
        if not success:
            return self._create_error_report()
        items = self.data_model.get_items()
        analyses = []
        for item in items:
            analysis = self.analyzer.analyze_item(item)
            analyses.append(analysis)
        self.report = self._build_report(analyses)
        return self.report

    def analyze_data(self, items: List[Dict]) -> NumistaIntelligenceReport:
        analyses = []
        for item in items:
            analysis = self.analyzer.analyze_item(item)
            analyses.append(analysis)
        self.report = self._build_report(analyses)
        return self.report

    def _build_report(self, analyses: List[NumistaItemAnalysis]) -> NumistaIntelligenceReport:
        report = NumistaIntelligenceReport(
            report_date=datetime.now().isoformat(),
            total_numista_items=len(analyses),
            analyzed_items=len(analyses),
            owned_count=sum(1 for a in analyses if a.status == NumistaMatchStatus.OWNED),
            duplicate_count=sum(1 for a in analyses if a.status == NumistaMatchStatus.DUPLICATE),
            upgrade_count=sum(1 for a in analyses if a.status == NumistaMatchStatus.UPGRADE),
            gap_count=sum(1 for a in analyses if a.status == NumistaMatchStatus.GAP),
            variety_count=sum(1 for a in analyses if a.status == NumistaMatchStatus.VARIETY),
            new_series_count=sum(1 for a in analyses if a.status == NumistaMatchStatus.NEW_SERIES),
            not_relevant_count=sum(1 for a in analyses if a.status == NumistaMatchStatus.NOT_RELEVANT),
            item_analyses=analyses,
        )
        self._build_duplicate_reports(report, analyses)
        self._build_upgrade_reports(report, analyses)
        self._build_gap_reports(report, analyses)
        priority_order = [NumistaPriority.CRITICAL, NumistaPriority.HIGH, NumistaPriority.MEDIUM]
        report.top_priorities = []
        for priority in priority_order:
            for analysis in analyses:
                if analysis.priority == priority and analysis.status not in [NumistaMatchStatus.OWNED, NumistaMatchStatus.DUPLICATE]:
                    report.top_priorities.append(analysis)
        report.summary_recommendations = self._generate_recommendations(report)
        validation = self.data_model.get_validation_summary()
        if validation['parse_errors'] > 0:
            report.warnings.append(f"{validation['parse_errors']} parse errors encountered")
        return report

    def _build_duplicate_reports(self, report: NumistaIntelligenceReport, analyses: List[NumistaItemAnalysis]):
        for analysis in analyses:
            if analysis.status == NumistaMatchStatus.DUPLICATE and analysis.matched_collection_item:
                for item in self.collection.items:
                    if item.id == analysis.matched_collection_item:
                        dup_report = NumistaDuplicateReport(
                            numista_item=analysis,
                            collection_item_id=item.id,
                            collection_item_title=item.title or f"{item.country} {item.year} {item.denomination}",
                            duplicate_reason="Same N# or country/year/reference match",
                            recommendation="Skip - already in collection",
                        )
                        report.duplicate_reports.append(dup_report)
                        break

    def _build_upgrade_reports(self, report: NumistaIntelligenceReport, analyses: List[NumistaItemAnalysis]):
        for analysis in analyses:
            if analysis.status == NumistaMatchStatus.UPGRADE and analysis.matched_collection_item:
                for item in self.collection.items:
                    if item.id == analysis.matched_collection_item:
                        upg_report = NumistaUpgradeReport(
                            numista_item=analysis,
                            existing_item_id=item.id,
                            existing_item_title=item.title or f"{item.country} {item.year} {item.denomination}",
                            existing_grade=item.grade,
                            proposed_grade=analysis.grade,
                            upgrade_reason=f"Better grade: {item.grade} -> {analysis.grade}",
                            priority=analysis.priority,
                        )
                        report.upgrade_reports.append(upg_report)
                        break

    def _build_gap_reports(self, report: NumistaIntelligenceReport, analyses: List[NumistaItemAnalysis]):
        series_items: Dict[str, List[NumistaItemAnalysis]] = {}
        for analysis in analyses:
            if analysis.series_relevance:
                if analysis.series_relevance not in series_items:
                    series_items[analysis.series_relevance] = []
                series_items[analysis.series_relevance].append(analysis)
        for series_name, items in series_items.items():
            gap_report = NumistaGapReport(
                series_name=series_name,
                owned_dates=[a.year for a in items if a.status == NumistaMatchStatus.OWNED],
                missing_dates=[a.year for a in items if a.status in [NumistaMatchStatus.GAP, NumistaMatchStatus.VARIETY]],
                completion_pct=0.0,
                want_list_count=0,
                numista_items_available=len(items),
                priority=NumistaPriority.HIGH if 'Newfoundland' in series_name else NumistaPriority.MEDIUM,
                recommendations=[f"Consider acquiring {len([a for a in items if a.status in [NumistaMatchStatus.GAP, NumistaMatchStatus.VARIETY]])} items for {series_name}"],
            )
            report.gap_reports.append(gap_report)

    def _generate_recommendations(self, report: NumistaIntelligenceReport) -> List[str]:
        recommendations = []
        if report.upgrade_count > 0:
            recommendations.append(f"Review {report.upgrade_count} upgrade opportunities")
        if report.gap_count > 0:
            recommendations.append(f"Consider {report.gap_count} collection gaps")
        if report.variety_count > 0:
            recommendations.append(f"Investigate {report.variety_count} variety opportunities")
        if report.duplicate_count > 0:
            recommendations.append(f"Skip {report.duplicate_count} duplicates")
        if report.new_series_count > 0:
            recommendations.append(f"Explore {report.new_series_count} new series opportunities")
        if not recommendations:
            recommendations.append("No immediate action required")
        return recommendations

    def _create_error_report(self) -> NumistaIntelligenceReport:
        return NumistaIntelligenceReport(
            report_date=datetime.now().isoformat(),
            total_numista_items=0,
            analyzed_items=0,
            owned_count=0,
            duplicate_count=0,
            upgrade_count=0,
            gap_count=0,
            variety_count=0,
            new_series_count=0,
            not_relevant_count=0,
            warnings=["Failed to load Numista data"] + self.data_model.parse_errors,
        )

    def export_report_csv(self, file_path: str):
        if not self.report:
            raise ValueError("No report to export. Run analyze_file() first.")
        import csv
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Numista N#', 'Title', 'Country', 'Year', 'Grade', 'Status', 'Priority', 'Reasons'])
            for analysis in self.report.item_analyses:
                writer.writerow([
                    analysis.numista_n,
                    analysis.title,
                    analysis.country,
                    analysis.year,
                    analysis.grade,
                    analysis.status.value,
                    analysis.priority.value,
                    '; '.join(analysis.reasons),
                ])

    def export_report_markdown(self, file_path: str):
        if not self.report:
            raise ValueError("No report to export. Run analyze_file() first.")
        lines = [
            "# Numista Intelligence Report",
            "",
            f"**Date:** {self.report.report_date}",
            f"**Total Items:** {self.report.total_numista_items}",
            "",
            "## Summary",
            f"- Owned: {self.report.owned_count}",
            f"- Duplicates: {self.report.duplicate_count}",
            f"- Upgrades: {self.report.upgrade_count}",
            f"- Gaps: {self.report.gap_count}",
            f"- Varieties: {self.report.variety_count}",
            f"- New Series: {self.report.new_series_count}",
            f"- Not Relevant: {self.report.not_relevant_count}",
            "",
            "## Recommendations",
        ]
        for rec in self.report.summary_recommendations:
            lines.append(f"- {rec}")
        if self.report.warnings:
            lines.extend(["", "## Warnings"])
            for warning in self.report.warnings:
                lines.append(f"- {warning}")
        if self.report.top_priorities:
            lines.extend(["", "## Top Priorities"])
            for i, analysis in enumerate(self.report.top_priorities[:10], 1):
                lines.append(f"{i}. **{analysis.title}** ({analysis.country} {analysis.year}) - {analysis.priority.value.upper()}")
                lines.append(f"   - Status: {analysis.status.value}")
                lines.append(f"   - Reasons: {', '.join(analysis.reasons)}")
        if self.report.upgrade_reports:
            lines.extend(["", "## Upgrade Opportunities"])
            for upg in self.report.upgrade_reports:
                lines.append(f"- **{upg.numista_item.title}** ({upg.numista_item.year})")
                lines.append(f"  - Upgrade: {upg.existing_grade} -> {upg.proposed_grade}")
                lines.append(f"  - Priority: {upg.priority.value}")
        if self.report.gap_reports:
            lines.extend(["", "## Gap Analysis"])
            for gap in self.report.gap_reports:
                lines.append(f"- **{gap.series_name}**")
                lines.append(f"  - Missing: {len(gap.missing_dates)} dates")
                lines.append(f"  - Priority: {gap.priority.value}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))


def run_numista_intelligence(file_path: str, collection_path: str = "data/collection.json") -> NumistaIntelligenceReport:
    collection = CoinCollection(collection_path)
    engine = NumistaIntelligenceEngine(collection)
    return engine.analyze_file(file_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        report = run_numista_intelligence(sys.argv[1])
        print(f"Numista Intelligence Report")
        print(f"Total: {report.total_numista_items}")
        print(f"Owned: {report.owned_count}")
        print(f"Upgrades: {report.upgrade_count}")
        print(f"Gaps: {report.gap_count}")
        print(f"\nTop Priorities:")
        for i, a in enumerate(report.top_priorities[:5], 1):
            print(f"  {i}. {a.title} ({a.status.value}, {a.priority.value})")
    else:
        print("Usage: python numista_intelligence.py <numista_export.xlsx>")
