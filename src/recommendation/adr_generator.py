"""
TrueArch Architecture Decision Record (ADR) Generator.

Converts a StackRecommendation into a committable Markdown ADR file.
Every ADR is:
  - Uniquely addressable by Genome short code + generated_at hash
  - Human-readable and directly committable into a repository as docs/adr/ADR-NNN.md
  - Contains full rationale, alternatives rejected, risks documented, and a review date

Innovation #3 from INNOVATION.md — "ADR Generator"
"""
from __future__ import annotations

import hashlib
from datetime import datetime, date
from typing import Optional

from src.recommendation.models import StackRecommendation


# Severity → emoji for risk display
_SEVERITY_ICON = {
    "critical": "🔴",
    "high":     "🔴",
    "medium":   "🟡",
    "low":      "🟢",
}


class ADRGenerator:
    """
    Generates Markdown Architecture Decision Records from TrueArch recommendations.

    Usage:
        generator = ADRGenerator()
        markdown = generator.generate(recommendation, adr_number=1)
        # Save to: docs/adr/ADR-001.md
    """

    def generate(
        self,
        recommendation: StackRecommendation,
        adr_number: int = 1,
        project_name: Optional[str] = None,
        team: Optional[str] = None,
    ) -> str:
        """
        Generate a Markdown ADR document from a StackRecommendation.

        Args:
            recommendation: The full StackRecommendation from the stack engine.
            adr_number:     Sequential ADR number for this project.
            project_name:   Optional project name to include in the ADR.
            team:           Optional team name.

        Returns:
            A complete Markdown string ready to be committed as ADR-NNN.md.
        """
        adr_id = self._generate_id(recommendation)
        today = date.today().isoformat()
        project_str = f" — {project_name}" if project_name else ""
        team_str = f"  \n**Team:** {team}" if team else ""

        lines = [
            f"# ADR-{adr_number:03d}: Stack Selection{project_str}",
            "",
            f"**Status:** Accepted  ",
            f"**Date:** {today}  ",
            f"**TrueArch Genome:** `{recommendation.genome_short or 'N/A'}`  ",
            f"**TrueArch Genome (Full):** `{recommendation.genome_full or 'N/A'}`  ",
            f"**TrueArch Confidence:** {recommendation.confidence:.0f}%  ",
            f"**TrueArch Score Band:** {recommendation.score_band}  ",
            f"**Review By:** {recommendation.review_by or 'N/A'}  ",
            f"**ADR ID:** `truearch/{adr_id}`  ",
            team_str,
            "",
            "---",
            "",
            "## Context",
            "",
            f"{recommendation.query_summary}",
            "",
            "---",
            "",
            "## Decision",
            "",
        ]

        # Primary framework choices per layer
        if recommendation.layers:
            lines.append("The following stack has been selected based on TrueArch analysis:\n")
            lines.append("| Layer | Framework | Version | Score | Confidence |")
            lines.append("|---|---|---|---|---|")
            for layer_name, choice in recommendation.layers.items():
                lines.append(
                    f"| **{layer_name.replace('_', ' ').title()}** "
                    f"| {choice.framework_name} "
                    f"| `{choice.version}` "
                    f"| {choice.score:.0f}/100 "
                    f"| {choice.confidence:.0f}% |"
                )
            lines.append("")

        lines += [
            "---",
            "",
            "## Rationale (TrueArch-Generated)",
            "",
        ]

        for layer_name, choice in recommendation.layers.items():
            lines.append(f"**{layer_name.replace('_', ' ').title()}:** {choice.reason}")
            if choice.alternatives:
                lines.append(
                    f"  - *Alternatives considered:* {', '.join(choice.alternatives)}"
                )
            lines.append("")

        # Tradeoff notes
        if recommendation.tradeoff_notes:
            lines += [
                "---",
                "",
                "## Tradeoffs Accepted",
                "",
            ]
            for note in recommendation.tradeoff_notes:
                lines.append(f"- {note}")
            lines.append("")

        # Risks and warnings
        if recommendation.global_warnings:
            lines += [
                "---",
                "",
                "## Risks Documented",
                "",
            ]
            for warning in recommendation.global_warnings:
                lines.append(f"- ⚠️  {warning}")
            lines.append("")

        # Alternatives rejected table
        alternatives_map = {}
        for layer_name, choice in recommendation.layers.items():
            for alt in choice.alternatives:
                if alt not in alternatives_map:
                    alternatives_map[alt] = f"Not the top-ranked choice in the {layer_name} layer"

        if alternatives_map:
            lines += [
                "---",
                "",
                "## Alternatives Rejected",
                "",
                "| Framework | Reason |",
                "|---|---|",
            ]
            for alt, reason in alternatives_map.items():
                lines.append(f"| {alt} | {reason} |")
            lines.append("")

        # Architecture Genome explanation
        if recommendation.genome_short:
            genome_parts = recommendation.genome_short.split("-")
            genome_dims = [
                "Architectural Pattern",
                "Memory Strategy",
                "Scaling Strategy",
                "Compliance Profile",
                "Primary Language",
                "Agent Protocol",
                "Primary Store",
            ]
            lines += [
                "---",
                "",
                "## Architecture Genome",
                "",
                f"**Genome:** `{recommendation.genome_short}`",
                "",
                "| Position | Dimension | Code | Meaning |",
                "|---|---|---|---|",
            ]
            for i, (code, dim) in enumerate(zip(genome_parts, genome_dims)):
                lines.append(f"| D{i+1} | {dim} | `{code}` | *(see GENOME_TAXONOMY.md)* |")
            lines.append("")
            lines.append(
                "> Search for teams with similar Genome profiles at "
                "`truearch.ai/genome/" + recommendation.genome_short + "`"
            )
            lines.append("")

        # Review section
        lines += [
            "---",
            "",
            "## Review Schedule",
            "",
            f"**Next Review Date:** {recommendation.review_by or 'N/A'}",
            "",
            "Re-evaluate this decision if:",
            "- Any framework's TrueArch Mortality Score drops below 60",
            "- A critical security advisory is issued for a chosen framework",
            "- Scale tier changes significantly (e.g. growth → enterprise)",
            "- A compliance regime changes (new regulations, scope expansion)",
            "",
            "---",
            "",
            f"*Generated by TrueArch Intelligence Engine on {today} "
            f"| Genome: {recommendation.genome_short or 'N/A'} "
            f"| ADR ID: truearch/{adr_id}*  ",
            "*Validate this recommendation at `truearch.ai` — scores refresh every 30 days.*",
        ]

        return "\n".join(lines)

    @staticmethod
    def _generate_id(recommendation: StackRecommendation) -> str:
        """Generate a short, stable ADR ID from Genome + generated_at."""
        raw = f"{recommendation.genome_short or 'NA'}-{recommendation.generated_at}"
        return hashlib.md5(raw.encode()).hexdigest()[:8]  # noqa: S324 — not for security
