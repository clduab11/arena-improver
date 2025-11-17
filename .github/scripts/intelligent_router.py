#!/usr/bin/env python3
"""
Intelligent Review Router

Context-aware routing based on file patterns, defect history, and blast radius.
Routes different types of changes to appropriate review modes for optimal efficiency.
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from github import Github
except ImportError:
    print("Warning: PyGithub not installed")


@dataclass
class RoutingDecision:
    """Review routing decision."""

    review_mode: str  # triage, standard, deep, security
    priority: int  # 1 (highest) to 5 (lowest)
    reason: str
    focus_areas: list[str]
    blast_radius_score: int
    defect_density_score: float


class IntelligentRouter:
    """Routes code reviews intelligently based on context."""

    def __init__(self, repo_name: str, github_token: str) -> None:
        """Initialize the router."""
        self.github = Github(github_token)
        self.repo = self.github.get_repo(repo_name)
        self.defect_history_file = ".github/defect_history.json"
        self.routing_rules_file = ".github/routing_rules.json"

    def route_pr(self, pr_number: int) -> RoutingDecision:
        """Route a PR to the appropriate review mode."""
        pr = self.repo.get_pull(pr_number)
        files = list(pr.get_files())

        # Calculate various scores
        blast_radius = self._calculate_blast_radius(files)
        defect_density = self._calculate_defect_density(files)
        file_importance = self._calculate_file_importance(files)
        security_risk = self._calculate_security_risk(files)

        # Determine review mode based on scores
        review_mode = self._determine_review_mode(
            blast_radius, defect_density, file_importance, security_risk
        )

        # Determine focus areas
        focus_areas = self._determine_focus_areas(files, pr)

        # Calculate priority
        priority = self._calculate_priority(
            blast_radius, defect_density, file_importance, security_risk
        )

        # Generate reasoning
        reason = self._generate_reason(
            review_mode, blast_radius, defect_density, file_importance, security_risk
        )

        return RoutingDecision(
            review_mode=review_mode,
            priority=priority,
            reason=reason,
            focus_areas=focus_areas,
            blast_radius_score=blast_radius,
            defect_density_score=defect_density,
        )

    def _calculate_blast_radius(self, files: list[Any]) -> int:
        """
        Calculate blast radius (number of files affected).

        Returns:
            Score 0-100, higher = larger blast radius
        """
        file_count = len(files)

        # Count lines changed
        total_changes = sum(f.additions + f.deletions for f in files)

        # Score based on file count and changes
        if file_count >= 10 or total_changes >= 500:
            return 90  # Very high
        elif file_count >= 5 or total_changes >= 200:
            return 70  # High
        elif file_count >= 3 or total_changes >= 100:
            return 50  # Medium
        elif file_count >= 2 or total_changes >= 50:
            return 30  # Low
        else:
            return 10  # Very low

    def _calculate_defect_density(self, files: list[Any]) -> float:
        """
        Calculate defect density based on historical bug data.

        Returns:
            Average bugs per file in last 30 days
        """
        # Load defect history
        history = self._load_defect_history()

        # Calculate defect density for each file
        densities = []
        cutoff_date = datetime.now() - timedelta(days=30)

        for file in files:
            file_path = file.filename
            file_defects = history.get(file_path, [])

            # Count recent defects
            recent_defects = sum(
                1
                for defect in file_defects
                if datetime.fromisoformat(defect["date"]) > cutoff_date
            )

            densities.append(recent_defects)

        return sum(densities) / len(densities) if densities else 0.0

    def _calculate_file_importance(self, files: list[Any]) -> int:
        """
        Calculate file importance based on patterns and CODEOWNERS.

        Returns:
            Score 0-100, higher = more important
        """
        # High importance patterns
        high_importance = [
            r".*auth.*\.py$",
            r".*security.*\.py$",
            r".*/api/.*\.py$",
            r".*/database/.*\.py$",
            r".*/models/.*\.py$",
            r".*settings.*\.py$",
            r".*config.*\.py$",
        ]

        # Medium importance patterns
        medium_importance = [
            r".*/services/.*\.py$",
            r".*/utils/.*\.py$",
            r".*__init__\.py$",
        ]

        # Low importance patterns
        low_importance = [
            r".*_test\.py$",
            r".*/tests/.*\.py$",
            r".*\.md$",
            r".*\.txt$",
        ]

        scores = []
        for file in files:
            file_path = file.filename

            # Check patterns
            if any(re.match(p, file_path) for p in high_importance):
                scores.append(90)
            elif any(re.match(p, file_path) for p in medium_importance):
                scores.append(50)
            elif any(re.match(p, file_path) for p in low_importance):
                scores.append(10)
            else:
                scores.append(30)  # Default

        return max(scores) if scores else 30

    def _calculate_security_risk(self, files: list[Any]) -> int:
        """
        Calculate security risk based on file patterns.

        Returns:
            Score 0-100, higher = higher security risk
        """
        # Security-sensitive patterns
        security_patterns = [
            r".*auth.*",
            r".*security.*",
            r".*crypto.*",
            r".*password.*",
            r".*token.*",
            r".*session.*",
            r".*permission.*",
            r".*api.*",
            r".*database.*",
            r".*sql.*",
        ]

        # Check files
        high_risk_count = 0
        for file in files:
            if any(re.search(p, file.filename, re.I) for p in security_patterns):
                high_risk_count += 1

        # Score based on proportion
        if not files:
            return 0

        risk_ratio = high_risk_count / len(files)

        if risk_ratio >= 0.5:
            return 90
        elif risk_ratio >= 0.25:
            return 70
        elif risk_ratio > 0:
            return 40
        else:
            return 10

    def _determine_review_mode(
        self,
        blast_radius: int,
        defect_density: float,
        file_importance: int,
        security_risk: int,
    ) -> str:
        """Determine the appropriate review mode."""
        # Security audit if high security risk
        if security_risk >= 70:
            return "security"

        # Deep analysis if high blast radius or importance
        if blast_radius >= 70 or file_importance >= 80:
            return "deep"

        # Standard review if medium risk or defect density
        if (
            blast_radius >= 40
            or defect_density >= 2.0
            or file_importance >= 50
            or security_risk >= 40
        ):
            return "standard"

        # Triage for low-risk changes
        return "triage"

    def _determine_focus_areas(self, files: list[Any], pr: Any) -> list[str]:
        """Determine which areas to focus the review on."""
        focus = set()

        # Analyze file patterns
        file_paths = [f.filename for f in files]

        # Frontend changes
        if any(".html" in f or ".css" in f or ".js" in f for f in file_paths):
            focus.add("ui_ux")

        # Backend changes
        if any(
            "api" in f or "service" in f or "database" in f
            for f in file_paths
        ):
            focus.add("backend")
            focus.add("performance")

        # Security files
        if any(
            "auth" in f or "security" in f or "crypto" in f
            for f in file_paths
        ):
            focus.add("security")

        # Test files
        if any("test" in f for f in file_paths):
            focus.add("testing")

        # Database changes
        if any("migration" in f or "sql" in f for f in file_paths):
            focus.add("database")
            focus.add("data_integrity")

        # Documentation
        if any(f.endswith(".md") for f in file_paths):
            focus.add("documentation")

        # Default focus areas
        if not focus:
            focus = {"code_quality", "bugs"}

        return sorted(list(focus))

    def _calculate_priority(
        self,
        blast_radius: int,
        defect_density: float,
        file_importance: int,
        security_risk: int,
    ) -> int:
        """
        Calculate review priority.

        Returns:
            1 (highest) to 5 (lowest)
        """
        # Weighted score
        score = (
            security_risk * 0.4
            + file_importance * 0.3
            + blast_radius * 0.2
            + min(defect_density * 10, 100) * 0.1
        )

        if score >= 80:
            return 1  # Critical
        elif score >= 60:
            return 2  # High
        elif score >= 40:
            return 3  # Medium
        elif score >= 20:
            return 4  # Low
        else:
            return 5  # Very low

    def _generate_reason(
        self,
        review_mode: str,
        blast_radius: int,
        defect_density: float,
        file_importance: int,
        security_risk: int,
    ) -> str:
        """Generate a human-readable reason for the routing decision."""
        reasons = []

        if security_risk >= 70:
            reasons.append(f"High security risk (score: {security_risk})")
        elif security_risk >= 40:
            reasons.append(f"Medium security risk (score: {security_risk})")

        if blast_radius >= 70:
            reasons.append(f"Large blast radius (score: {blast_radius})")
        elif blast_radius >= 40:
            reasons.append(f"Medium blast radius (score: {blast_radius})")

        if defect_density >= 3.0:
            reasons.append(f"High defect density ({defect_density:.1f} bugs/file)")
        elif defect_density >= 1.5:
            reasons.append(f"Medium defect density ({defect_density:.1f} bugs/file)")

        if file_importance >= 80:
            reasons.append(f"Critical files affected (importance: {file_importance})")
        elif file_importance >= 50:
            reasons.append(f"Important files affected (importance: {file_importance})")

        if not reasons:
            reasons.append("Standard review criteria")

        return f"Routed to {review_mode} mode: " + "; ".join(reasons)

    def _load_defect_history(self) -> dict[str, list[dict]]:
        """Load defect history from file."""
        if os.path.exists(self.defect_history_file):
            with open(self.defect_history_file, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def update_defect_history(self, file_path: str, defect_type: str) -> None:
        """Update defect history when a bug is found."""
        history = self._load_defect_history()

        if file_path not in history:
            history[file_path] = []

        history[file_path].append(
            {"date": datetime.now().isoformat(), "type": defect_type}
        )

        # Keep only last 90 days
        cutoff = datetime.now() - timedelta(days=90)
        history[file_path] = [
            d
            for d in history[file_path]
            if datetime.fromisoformat(d["date"]) > cutoff
        ]

        # Save
        os.makedirs(os.path.dirname(self.defect_history_file), exist_ok=True)
        with open(self.defect_history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Intelligent Review Router")
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("Error: GITHUB_TOKEN not set")
        return

    router = IntelligentRouter(args.repo, github_token)
    decision = router.route_pr(args.pr_number)

    # Output routing decision as JSON
    output = {
        "review_mode": decision.review_mode,
        "priority": decision.priority,
        "reason": decision.reason,
        "focus_areas": decision.focus_areas,
        "blast_radius_score": decision.blast_radius_score,
        "defect_density_score": decision.defect_density_score,
    }

    print(json.dumps(output, indent=2))

    # Save to file for GitHub Actions
    with open("routing_decision.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)


if __name__ == "__main__":
    main()
