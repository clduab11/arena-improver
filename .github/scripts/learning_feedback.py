#!/usr/bin/env python3
"""
Learning Feedback Loop

Tracks which Claude suggestions get accepted/rejected and generates
effectiveness reports to improve future reviews.
"""

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from github import Github
except ImportError:
    print("Warning: PyGithub not installed")


@dataclass
class ReviewFeedback:
    """Feedback on a review suggestion."""

    suggestion_id: str
    review_id: str
    pr_number: int
    suggestion_type: str  # security, performance, style, etc.
    severity: str
    accepted: bool
    timestamp: datetime
    file_path: str
    suggestion_text: str
    developer_comment: str | None = None


class LearningFeedbackSystem:
    """Tracks and learns from review feedback."""

    def __init__(self, repo_name: str, github_token: str | None = None) -> None:
        """Initialize the feedback system."""
        self.repo_name = repo_name
        self.feedback_file = ".github/claude_feedback.json"
        self.patterns_file = ".github/learned_patterns.json"
        self.changelog_file = "CHANGELOG.md"

        if github_token:
            self.github = Github(github_token)
            self.repo = self.github.get_repo(repo_name)
        else:
            self.github = None
            self.repo = None

    def record_feedback(
        self,
        pr_number: int,
        suggestion_id: str,
        accepted: bool,
        suggestion_data: dict[str, Any],
    ) -> None:
        """Record feedback on a suggestion."""
        feedback = ReviewFeedback(
            suggestion_id=suggestion_id,
            review_id=suggestion_data.get("review_id", ""),
            pr_number=pr_number,
            suggestion_type=suggestion_data.get("type", "unknown"),
            severity=suggestion_data.get("severity", "medium"),
            accepted=accepted,
            timestamp=datetime.now(),
            file_path=suggestion_data.get("file_path", ""),
            suggestion_text=suggestion_data.get("text", ""),
            developer_comment=suggestion_data.get("comment"),
        )

        # Load existing feedback
        all_feedback = self._load_feedback()
        all_feedback.append(self._feedback_to_dict(feedback))

        # Save updated feedback
        self._save_feedback(all_feedback)

        # Update learned patterns
        self._update_patterns(feedback)

    def analyze_commit_acceptance(self, pr_number: int) -> dict[str, Any]:
        """
        Analyze which suggestions were actually committed.

        Compares Claude's suggestions with actual commits to determine
        acceptance rate automatically.
        """
        if not self.repo:
            return {}

        pr = self.repo.get_pull(pr_number)
        commits = list(pr.get_commits())

        # Get review suggestions
        suggestions = self._get_pr_suggestions(pr_number)

        # Analyze commits
        accepted_count = 0
        for suggestion in suggestions:
            if self._was_suggestion_implemented(suggestion, commits):
                accepted_count += 1
                self.record_feedback(
                    pr_number=pr_number,
                    suggestion_id=suggestion["id"],
                    accepted=True,
                    suggestion_data=suggestion,
                )

        return {
            "total_suggestions": len(suggestions),
            "accepted": accepted_count,
            "acceptance_rate": accepted_count / len(suggestions) if suggestions else 0,
        }

    def generate_effectiveness_report(
        self, days: int = 30
    ) -> dict[str, Any]:
        """Generate monthly effectiveness report."""
        all_feedback = self._load_feedback()

        # Filter to date range
        cutoff = datetime.now() - timedelta(days=days)
        recent_feedback = [
            f
            for f in all_feedback
            if datetime.fromisoformat(f["timestamp"]) > cutoff
        ]

        if not recent_feedback:
            return {"error": "No feedback data available"}

        # Calculate metrics
        total = len(recent_feedback)
        accepted = sum(1 for f in recent_feedback if f["accepted"])
        acceptance_rate = accepted / total if total > 0 else 0

        # By suggestion type
        by_type = defaultdict(lambda: {"total": 0, "accepted": 0})
        for f in recent_feedback:
            suggestion_type = f["suggestion_type"]
            by_type[suggestion_type]["total"] += 1
            if f["accepted"]:
                by_type[suggestion_type]["accepted"] += 1

        # Calculate acceptance rate by type
        type_rates = {}
        for stype, data in by_type.items():
            type_rates[stype] = {
                "total": data["total"],
                "accepted": data["accepted"],
                "acceptance_rate": data["accepted"] / data["total"],
            }

        # By severity
        by_severity = defaultdict(lambda: {"total": 0, "accepted": 0})
        for f in recent_feedback:
            severity = f["severity"]
            by_severity[severity]["total"] += 1
            if f["accepted"]:
                by_severity[severity]["accepted"] += 1

        severity_rates = {}
        for sev, data in by_severity.items():
            severity_rates[sev] = {
                "total": data["total"],
                "accepted": data["accepted"],
                "acceptance_rate": data["accepted"] / data["total"],
            }

        # False positive patterns
        false_positives = [f for f in recent_feedback if not f["accepted"]]
        false_positive_patterns = self._detect_false_positive_patterns(false_positives)

        report = {
            "period_days": days,
            "generated_at": datetime.now().isoformat(),
            "overall": {
                "total_suggestions": total,
                "accepted": accepted,
                "rejected": total - accepted,
                "acceptance_rate": acceptance_rate,
            },
            "by_type": type_rates,
            "by_severity": severity_rates,
            "false_positive_patterns": false_positive_patterns,
            "top_rejected_types": sorted(
                [
                    (t, 1 - d["acceptance_rate"])
                    for t, d in type_rates.items()
                ],
                key=lambda x: x[1],
                reverse=True,
            )[:5],
        }

        return report

    def load_changelog_context(self) -> list[str]:
        """
        Load intentional architectural choices from CHANGELOG.

        Extracts patterns that Claude should not flag as issues.
        """
        if not os.path.exists(self.changelog_file):
            return []

        with open(self.changelog_file, encoding="utf-8") as f:
            changelog = f.read()

        # Extract intentional decisions
        intentional_patterns = []

        # Look for "intentional" or "by design" patterns
        lines = changelog.split("\n")
        for i, line in enumerate(lines):
            if any(
                keyword in line.lower()
                for keyword in ["intentional", "by design", "architectural decision"]
            ):
                # Include context (previous and next lines)
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 3)
                context = " ".join(lines[context_start:context_end])
                intentional_patterns.append(context)

        return intentional_patterns

    def _load_feedback(self) -> list[dict[str, Any]]:
        """Load feedback from storage."""
        if os.path.exists(self.feedback_file):
            with open(self.feedback_file, encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_feedback(self, feedback: list[dict[str, Any]]) -> None:
        """Save feedback to storage."""
        os.makedirs(os.path.dirname(self.feedback_file), exist_ok=True)
        with open(self.feedback_file, "w", encoding="utf-8") as f:
            json.dump(feedback, f, indent=2)

    def _feedback_to_dict(self, feedback: ReviewFeedback) -> dict[str, Any]:
        """Convert feedback object to dict."""
        return {
            "suggestion_id": feedback.suggestion_id,
            "review_id": feedback.review_id,
            "pr_number": feedback.pr_number,
            "suggestion_type": feedback.suggestion_type,
            "severity": feedback.severity,
            "accepted": feedback.accepted,
            "timestamp": feedback.timestamp.isoformat(),
            "file_path": feedback.file_path,
            "suggestion_text": feedback.suggestion_text,
            "developer_comment": feedback.developer_comment,
        }

    def _update_patterns(self, feedback: ReviewFeedback) -> None:
        """Update learned patterns based on feedback."""
        patterns = self._load_patterns()

        # Track rejection patterns
        if not feedback.accepted:
            pattern_key = f"{feedback.suggestion_type}:{feedback.file_path}"

            if pattern_key not in patterns["rejections"]:
                patterns["rejections"][pattern_key] = {
                    "count": 0,
                    "suggestion_type": feedback.suggestion_type,
                    "file_pattern": feedback.file_path,
                    "examples": [],
                }

            patterns["rejections"][pattern_key]["count"] += 1
            patterns["rejections"][pattern_key]["examples"].append(
                {
                    "pr": feedback.pr_number,
                    "text": feedback.suggestion_text[:200],
                }
            )

        # Track acceptance patterns
        else:
            pattern_key = f"{feedback.suggestion_type}"
            if pattern_key not in patterns["acceptances"]:
                patterns["acceptances"][pattern_key] = {"count": 0}
            patterns["acceptances"][pattern_key]["count"] += 1

        self._save_patterns(patterns)

    def _load_patterns(self) -> dict[str, Any]:
        """Load learned patterns."""
        if os.path.exists(self.patterns_file):
            with open(self.patterns_file, encoding="utf-8") as f:
                return json.load(f)
        return {"rejections": {}, "acceptances": {}}

    def _save_patterns(self, patterns: dict[str, Any]) -> None:
        """Save learned patterns."""
        os.makedirs(os.path.dirname(self.patterns_file), exist_ok=True)
        with open(self.patterns_file, "w", encoding="utf-8") as f:
            json.dump(patterns, f, indent=2)

    def _get_pr_suggestions(self, pr_number: int) -> list[dict[str, Any]]:
        """Get Claude's suggestions for a PR."""
        # Load from review artifacts if available
        review_file = f".github/reviews/pr_{pr_number}_review.json"
        if os.path.exists(review_file):
            with open(review_file, encoding="utf-8") as f:
                review_data = json.load(f)
                return review_data.get("suggestions", [])
        return []

    def _was_suggestion_implemented(
        self, suggestion: dict[str, Any], commits: list[Any]
    ) -> bool:
        """Check if a suggestion was implemented in commits."""
        # Simple heuristic: check if suggested code appears in commits
        suggested_code = suggestion.get("suggested_code", "")
        if not suggested_code:
            return False

        for commit in commits:
            if suggested_code in commit.commit.message:
                return True

            # Check file diffs
            for file in commit.files:
                if file.patch and suggested_code in file.patch:
                    return True

        return False

    def _detect_false_positive_patterns(
        self, false_positives: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect common false positive patterns."""
        # Group by suggestion type
        by_type = defaultdict(list)
        for fp in false_positives:
            by_type[fp["suggestion_type"]].append(fp)

        patterns = []
        for stype, fps in by_type.items():
            if len(fps) >= 3:  # At least 3 occurrences
                patterns.append(
                    {
                        "type": stype,
                        "count": len(fps),
                        "examples": [fp["suggestion_text"][:100] for fp in fps[:3]],
                        "recommendation": f"Consider adjusting sensitivity for {stype} checks",
                    }
                )

        return patterns


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Learning Feedback System")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--days", type=int, default=30, help="Report period in days")
    args = parser.parse_args()

    github_token = os.getenv("GITHUB_TOKEN")
    system = LearningFeedbackSystem(args.repo, github_token)

    if args.report:
        report = system.generate_effectiveness_report(args.days)

        # Save report
        with open("effectiveness_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        # Print summary
        print("\n" + "=" * 80)
        print(f"Review Effectiveness Report ({args.days} days)")
        print("=" * 80)
        print(f"\nOverall Acceptance Rate: {report['overall']['acceptance_rate']:.1%}")
        print(f"Total Suggestions: {report['overall']['total_suggestions']}")
        print(f"Accepted: {report['overall']['accepted']}")
        print(f"Rejected: {report['overall']['rejected']}")

        print("\nTop Suggestion Types:")
        for stype, data in list(report["by_type"].items())[:5]:
            print(f"  {stype}: {data['acceptance_rate']:.1%} ({data['accepted']}/{data['total']})")

        if report.get("false_positive_patterns"):
            print("\nFalse Positive Patterns Detected:")
            for pattern in report["false_positive_patterns"][:3]:
                print(f"  - {pattern['type']}: {pattern['count']} occurrences")

        print("=" * 80)


if __name__ == "__main__":
    main()
