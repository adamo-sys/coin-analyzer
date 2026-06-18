"""Mobile readiness audit helpers for future collector workflows.

This module does not build a mobile app, web app, API, scraper, OCR pipeline,
or market-pricing integration. It documents and scores the current desktop
architecture so future mobile work can start from explicit service boundaries.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MobileReadinessFinding:
    area: str
    status: str
    detail: str
    abstraction_point: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "area": self.area,
            "status": self.status,
            "detail": self.detail,
            "abstraction_point": self.abstraction_point,
            "recommendation": self.recommendation,
        }


@dataclass
class ServiceBoundaryFinding:
    service: str
    business_logic: str
    presentation_logic: str
    boundary_status: str
    mobile_notes: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service,
            "business_logic": self.business_logic,
            "presentation_logic": self.presentation_logic,
            "boundary_status": self.boundary_status,
            "mobile_notes": self.mobile_notes,
            "recommendation": self.recommendation,
        }


@dataclass
class MobileInputFinding:
    workflow: str
    supported: bool
    mobile_friction: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow": self.workflow,
            "supported": self.supported,
            "mobile_friction": self.mobile_friction,
            "recommendation": self.recommendation,
        }


@dataclass
class ApiEndpointMapping:
    endpoint: str
    purpose: str
    existing_source: str
    input_model: str
    output_model: str
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "purpose": self.purpose,
            "existing_source": self.existing_source,
            "input_model": self.input_model,
            "output_model": self.output_model,
            "notes": self.notes,
        }


@dataclass
class PhoneWorkflowStep:
    step_number: int
    action: str
    current_tool: str
    friction: str
    improvement: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "current_tool": self.current_tool,
            "friction": self.friction,
            "improvement": self.improvement,
        }


@dataclass
class MobileReadinessScore:
    architecture: int
    workflow: int
    persistence: int
    exports: int
    inputs: int
    strengths: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    @property
    def overall_score(self) -> int:
        values = [self.architecture, self.workflow, self.persistence, self.exports, self.inputs]
        return round(sum(values) / len(values))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "architecture": self.architecture,
            "workflow": self.workflow,
            "persistence": self.persistence,
            "exports": self.exports,
            "inputs": self.inputs,
            "strengths": list(self.strengths),
            "blockers": list(self.blockers),
            "recommendations": list(self.recommendations),
        }


@dataclass
class MobileReadinessReport:
    desktop_dependencies: List[MobileReadinessFinding] = field(default_factory=list)
    service_boundaries: List[ServiceBoundaryFinding] = field(default_factory=list)
    mobile_inputs: List[MobileInputFinding] = field(default_factory=list)
    api_mappings: List[ApiEndpointMapping] = field(default_factory=list)
    phone_workflow: List[PhoneWorkflowStep] = field(default_factory=list)
    score: MobileReadinessScore = field(
        default_factory=lambda: MobileReadinessScore(0, 0, 0, 0, 0)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "desktop_dependencies": [finding.to_dict() for finding in self.desktop_dependencies],
            "service_boundaries": [finding.to_dict() for finding in self.service_boundaries],
            "mobile_inputs": [finding.to_dict() for finding in self.mobile_inputs],
            "api_mappings": [mapping.to_dict() for mapping in self.api_mappings],
            "phone_workflow": [step.to_dict() for step in self.phone_workflow],
            "score": self.score.to_dict(),
        }


class MobileReadinessAuditor:
    """Generate a deterministic audit of mobile-readiness constraints."""

    def generate_report(self) -> MobileReadinessReport:
        return MobileReadinessReport(
            desktop_dependencies=self.desktop_dependency_audit(),
            service_boundaries=self.service_boundary_review(),
            mobile_inputs=self.mobile_input_readiness(),
            api_mappings=self.api_readiness_mapping(),
            phone_workflow=self.phone_workflow_audit(),
            score=self.mobile_readiness_score(),
        )

    def desktop_dependency_audit(self) -> List[MobileReadinessFinding]:
        return [
            MobileReadinessFinding(
                area="Tkinter GUI",
                status="BLOCKER",
                detail="The current primary interface is a desktop Tkinter application.",
                abstraction_point="Keep collector workflows behind service classes; isolate Tkinter in coin_collection_gui.py.",
                recommendation="Future mobile UI should call existing services instead of porting Tkinter windows.",
            ),
            MobileReadinessFinding(
                area="File dialogs",
                status="BLOCKER",
                detail="Workbook, export, backup, and photo paths are selected with desktop file dialogs.",
                abstraction_point="Create a file-picker/storage adapter before mobile implementation.",
                recommendation="Support mobile document providers and app-scoped storage in a future release.",
            ),
            MobileReadinessFinding(
                area="Workbook loading",
                status="PARTIAL",
                detail="Legacy portfolio parsing is service-level, but assumes local workbook file paths.",
                abstraction_point="Separate workbook bytes/source handles from desktop paths.",
                recommendation="Add an import source abstraction before accepting mobile-uploaded workbooks.",
            ),
            MobileReadinessFinding(
                area="Export workflows",
                status="PARTIAL",
                detail="CSV and Markdown exports are reusable, but write to local filesystem paths.",
                abstraction_point="Route exports through a storage/share destination adapter.",
                recommendation="Preserve CSV/Markdown generation and adapt only the output destination.",
            ),
            MobileReadinessFinding(
                area="Photo workflows",
                status="PARTIAL",
                detail="Photo Vault tracks local paths and metadata without moving files.",
                abstraction_point="Represent photos with portable URIs plus optional local path metadata.",
                recommendation="Add photo URI support before mobile camera/gallery integration.",
            ),
            MobileReadinessFinding(
                area="Persistence workflows",
                status="PARTIAL",
                detail="App state is JSON-based and suitable for mobile, but stored in project folders.",
                abstraction_point="Inject app-state storage location through PersistenceManager configuration.",
                recommendation="Map JSON persistence to app-scoped mobile storage in a future release.",
            ),
        ]

    def service_boundary_review(self) -> List[ServiceBoundaryFinding]:
        return [
            ServiceBoundaryFinding(
                service="Collection Intelligence",
                business_logic="Candidate ownership, duplicate, upgrade, gap, and WANT_LIST classification.",
                presentation_logic="None in core engine; GUI formats results separately.",
                boundary_status="READY",
                mobile_notes="Strong candidate for a future analyze_candidate endpoint.",
                recommendation="Keep this as the single decision source for ownership and upgrade status.",
            ),
            ServiceBoundaryFinding(
                service="Listing Analyzer",
                business_logic="Offline listing model, URL validation, total cost, acquisition conversion.",
                presentation_logic="Tkinter entry form exists separately.",
                boundary_status="READY",
                mobile_notes="Manual title, URL, price, and shipping entry map well to mobile.",
                recommendation="Preserve offline URL storage; do not add scraping in mobile readiness work.",
            ),
            ServiceBoundaryFinding(
                service="Smart Shopping Assistant",
                business_logic="Ranks candidate opportunities using acquisition impact and local context.",
                presentation_logic="Report/export formatting only.",
                boundary_status="READY",
                mobile_notes="Useful for shopping_recommendations endpoint.",
                recommendation="Keep ranking deterministic and input-driven.",
            ),
            ServiceBoundaryFinding(
                service="Collection Dashboard",
                business_logic="Aggregates collection, quality, series, market, photo, and shopping summaries.",
                presentation_logic="Markdown/CSV export formatting.",
                boundary_status="PARTIAL",
                mobile_notes="Summary data is reusable; desktop export destination is not mobile-ready.",
                recommendation="Expose dashboard data objects separately from local file exports.",
            ),
            ServiceBoundaryFinding(
                service="Collection Health Report",
                business_logic="Combines dashboard, quality, series, shopping, market, and persistence findings.",
                presentation_logic="Markdown/CSV export formatting.",
                boundary_status="PARTIAL",
                mobile_notes="Suitable for collection_health endpoint after storage abstraction.",
                recommendation="Keep report data structured for API serialization.",
            ),
            ServiceBoundaryFinding(
                service="Persistence Layer",
                business_logic="JSON app state save, load, validate, backup, import, and export.",
                presentation_logic="None in core manager.",
                boundary_status="PARTIAL",
                mobile_notes="JSON model is portable; path assumptions are desktop-specific.",
                recommendation="Introduce storage-provider configuration before mobile persistence.",
            ),
            ServiceBoundaryFinding(
                service="Backup Manager",
                business_logic="Backup packages, manifests, verification, restore, validation, export bundle.",
                presentation_logic="Tools menu calls manager actions.",
                boundary_status="PARTIAL",
                mobile_notes="Zip packages are portable, but restore paths and project-root assumptions are desktop-specific.",
                recommendation="Keep backup verification logic and adapt filesystem package destinations for mobile.",
            ),
        ]

    def mobile_input_readiness(self) -> List[MobileInputFinding]:
        return [
            MobileInputFinding(
                workflow="Manual candidate entry",
                supported=True,
                mobile_friction="Many fields are useful but slower at a dealer table on a phone.",
                recommendation="Future mobile UI should offer a compact dealer-table entry mode.",
            ),
            MobileInputFinding(
                workflow="Pasted listing text",
                supported=True,
                mobile_friction="Large text areas can be awkward on small screens.",
                recommendation="Keep paste support and add focused title/price parsing only if deterministic.",
            ),
            MobileInputFinding(
                workflow="Pasted URLs",
                supported=True,
                mobile_friction="URL is stored as reference data only; no page enrichment is available.",
                recommendation="Continue storing URLs offline; future enrichment must remain opt-in.",
            ),
            MobileInputFinding(
                workflow="Photo references",
                supported=True,
                mobile_friction="Photo Vault uses local paths rather than mobile camera/gallery URIs.",
                recommendation="Add portable photo URI metadata before mobile camera workflows.",
            ),
            MobileInputFinding(
                workflow="Persisted context",
                supported=True,
                mobile_friction="Saved JSON state works, but current paths point to desktop project folders.",
                recommendation="Persist last-used context through a mobile storage adapter.",
            ),
        ]

    def api_readiness_mapping(self) -> List[ApiEndpointMapping]:
        return [
            ApiEndpointMapping(
                endpoint="analyze_candidate",
                purpose="Return ownership, duplicate, upgrade, WANT_LIST, and acquisition recommendation details.",
                existing_source="CollectionIntelligenceEngine, AcquisitionWorkflow, AcquisitionImpactEngine",
                input_model="Candidate fields plus optional asking price and WANT_LIST context.",
                output_model="Structured match status, recommendation, confidence, reasons, warnings.",
                notes="Documentation only; no API implemented in v2.3.",
            ),
            ApiEndpointMapping(
                endpoint="collection_health",
                purpose="Return collection health, quality, series, persistence, and priority summaries.",
                existing_source="CollectionHealthReportEngine",
                input_model="Collection items, WANT_LIST intents, market records, photo records, shopping candidates.",
                output_model="CollectionHealthReport",
                notes="Would need storage abstraction before mobile deployment.",
            ),
            ApiEndpointMapping(
                endpoint="shopping_recommendations",
                purpose="Rank shopping candidates and explain the best acquisition opportunities.",
                existing_source="SmartShoppingAssistant",
                input_model="ShoppingCandidate list plus active collection context.",
                output_model="ShoppingRecommendationReport",
                notes="Offline deterministic ranking only.",
            ),
            ApiEndpointMapping(
                endpoint="dashboard_summary",
                purpose="Return collector-facing dashboard panels and snapshot metrics.",
                existing_source="CollectionDashboard",
                input_model="Collection items and optional WANT_LIST, market, photo, and shopping context.",
                output_model="CollectionDashboardData",
                notes="Dashboard data is already structured; exports remain filesystem-dependent.",
            ),
        ]

    def phone_workflow_audit(self) -> List[PhoneWorkflowStep]:
        return [
            PhoneWorkflowStep(
                step_number=1,
                action="Open app and restore or load collection context.",
                current_tool="Shared Session Context / Persistence Layer",
                friction="Desktop app startup and local workbook paths do not translate directly to a phone.",
                improvement="Auto-restore mobile app state from app-scoped JSON storage.",
            ),
            PhoneWorkflowStep(
                step_number=2,
                action="Open Listing Analyzer or Do I Own This?",
                current_tool="Tools menu",
                friction="Desktop menu navigation is workable but not optimized for dealer-table speed.",
                improvement="Provide a future single-tap dealer-table analysis entry point.",
            ),
            PhoneWorkflowStep(
                step_number=3,
                action="Enter country, denomination, year, grade, and asking price.",
                current_tool="Manual candidate entry",
                friction="Full manual entry can take several taps on a phone.",
                improvement="Use compact required fields first, then optional details.",
            ),
            PhoneWorkflowStep(
                step_number=4,
                action="Run candidate/acquisition analysis.",
                current_tool="Collection Intelligence / Acquisition Workflow",
                friction="Core analysis is ready; UI invocation is desktop-bound.",
                improvement="Expose the same service call behind a future mobile action.",
            ),
            PhoneWorkflowStep(
                step_number=5,
                action="Review ownership, duplicate, upgrade, WANT_LIST, and impact status.",
                current_tool="Do I Own This? / Listing Analyzer",
                friction="Dense desktop reports need a compact mobile summary.",
                improvement="Show verdict first, then expandable reasons.",
            ),
            PhoneWorkflowStep(
                step_number=6,
                action="Decide BUY, PASS, WATCH, NEGOTIATE, or REVIEW.",
                current_tool="Acquisition Workflow",
                friction="Decision logic is available, but not yet packaged as a mobile workflow.",
                improvement="Surface recommendation and max rational price as the first result block.",
            ),
        ]

    def mobile_readiness_score(self) -> MobileReadinessScore:
        return MobileReadinessScore(
            architecture=72,
            workflow=62,
            persistence=76,
            exports=68,
            inputs=64,
            strengths=[
                "Most collector decisions already live in reusable service classes.",
                "Collection Intelligence and Acquisition Workflow are deterministic and testable.",
                "JSON persistence and CSV/Markdown reports are portable foundations.",
                "Listing Analyzer already supports pasted text, pasted URLs, and manual price entry.",
            ],
            blockers=[
                "Primary UI is Tkinter and desktop-only.",
                "File dialogs and local filesystem paths are embedded in GUI workflows.",
                "Photo Vault currently stores local paths instead of portable mobile URIs.",
                "No API or mobile storage adapter exists yet.",
            ],
            recommendations=[
                "Create storage and file-picker adapters before mobile implementation.",
                "Keep service engines independent from Tkinter and local export destinations.",
                "Design future mobile screens around analyze_candidate and dashboard_summary outputs.",
                "Add a compact dealer-table workflow after storage abstraction is complete.",
            ],
        )

    def format_markdown(self) -> str:
        report = self.generate_report()
        lines = [
            "# Mobile Readiness Report",
            "",
            "## Mobile Readiness Score",
            "",
            f"- Overall score: {report.score.overall_score}",
            f"- Architecture: {report.score.architecture}",
            f"- Workflow: {report.score.workflow}",
            f"- Persistence: {report.score.persistence}",
            f"- Exports: {report.score.exports}",
            f"- Inputs: {report.score.inputs}",
            "",
            "## Strengths",
            "",
        ]
        lines.extend(f"- {item}" for item in report.score.strengths)
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {item}" for item in report.score.blockers)
        lines.extend(["", "## Recommendations", ""])
        lines.extend(f"- {item}" for item in report.score.recommendations)
        lines.extend(["", "## Desktop Dependency Audit", ""])
        for finding in report.desktop_dependencies:
            lines.append(f"- {finding.area} [{finding.status}]: {finding.detail}")
            lines.append(f"  - Abstraction point: {finding.abstraction_point}")
            lines.append(f"  - Recommendation: {finding.recommendation}")
        lines.extend(["", "## Service Boundary Review", ""])
        for finding in report.service_boundaries:
            lines.append(f"- {finding.service} [{finding.boundary_status}]: {finding.mobile_notes}")
            lines.append(f"  - Business logic: {finding.business_logic}")
            lines.append(f"  - Presentation logic: {finding.presentation_logic}")
        lines.extend(["", "## Mobile Input Readiness", ""])
        for finding in report.mobile_inputs:
            support = "supported" if finding.supported else "not supported"
            lines.append(f"- {finding.workflow}: {support}. {finding.mobile_friction}")
        lines.extend(["", "## API Readiness Mapping", ""])
        for mapping in report.api_mappings:
            lines.append(f"- {mapping.endpoint}: {mapping.purpose}")
            lines.append(f"  - Source: {mapping.existing_source}")
        lines.extend(["", "## Phone Workflow Audit", ""])
        for step in report.phone_workflow:
            lines.append(f"{step.step_number}. {step.action}")
            lines.append(f"   - Current tool: {step.current_tool}")
            lines.append(f"   - Friction: {step.friction}")
            lines.append(f"   - Improvement: {step.improvement}")
        return "\n".join(lines) + "\n"

    def export_markdown(self, output_path: str) -> bool:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(self.format_markdown())
            return True
        except Exception as exc:
            print(f"Error exporting mobile readiness markdown: {exc}")
            return False

    def export_csv(self, output_path: str) -> bool:
        try:
            report = self.generate_report()
            with open(output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Section", "Name", "Status", "Detail", "Recommendation"])
                writer.writerow(["Score", "Overall", report.score.overall_score, "", ""])
                writer.writerow(["Score", "Architecture", report.score.architecture, "", ""])
                writer.writerow(["Score", "Workflow", report.score.workflow, "", ""])
                writer.writerow(["Score", "Persistence", report.score.persistence, "", ""])
                writer.writerow(["Score", "Exports", report.score.exports, "", ""])
                writer.writerow(["Score", "Inputs", report.score.inputs, "", ""])
                for finding in report.desktop_dependencies:
                    writer.writerow([
                        "Desktop Dependency",
                        finding.area,
                        finding.status,
                        finding.detail,
                        finding.recommendation,
                    ])
                for finding in report.service_boundaries:
                    writer.writerow([
                        "Service Boundary",
                        finding.service,
                        finding.boundary_status,
                        finding.mobile_notes,
                        finding.recommendation,
                    ])
                for finding in report.mobile_inputs:
                    writer.writerow([
                        "Mobile Input",
                        finding.workflow,
                        "SUPPORTED" if finding.supported else "NOT_SUPPORTED",
                        finding.mobile_friction,
                        finding.recommendation,
                    ])
                for mapping in report.api_mappings:
                    writer.writerow([
                        "API Mapping",
                        mapping.endpoint,
                        "DOCUMENTED",
                        mapping.purpose,
                        mapping.notes,
                    ])
                for step in report.phone_workflow:
                    writer.writerow([
                        "Phone Workflow",
                        step.step_number,
                        step.current_tool,
                        step.friction,
                        step.improvement,
                    ])
            return True
        except Exception as exc:
            print(f"Error exporting mobile readiness CSV: {exc}")
            return False
