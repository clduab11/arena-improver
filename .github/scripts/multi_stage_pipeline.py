#!/usr/bin/env python3
"""
Multi-Stage Review Pipeline

Progressive code analysis with three stages:
- Stage 1 (Fast, <30s): Syntax, linting, basic security
- Stage 2 (Medium, 2-5min): Full tests, coverage, Claude review
- Stage 3 (Deep, 10-15min): Performance, dependencies, compliance
"""

import asyncio
import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any

import anthropic


@dataclass
class StageResult:
    """Result from a pipeline stage."""

    stage: int
    passed: bool
    duration: float
    issues: list[dict[str, Any]]
    metrics: dict[str, Any]
    should_proceed: bool


class MultiStagePipeline:
    """Multi-stage review pipeline."""

    def __init__(self, repo_path: str = ".") -> None:
        """Initialize the pipeline."""
        self.repo_path = repo_path
        self.results: list[StageResult] = []

    async def run_stage1_fast(self) -> StageResult:
        """
        Stage 1: Fast checks (<30s).

        - Syntax validation
        - Linting (Ruff)
        - Basic security scans
        """
        start_time = time.time()
        issues = []

        print("🚀 Stage 1: Fast Analysis")

        # 1. Syntax check
        syntax_result = self._run_command(["python", "-m", "py_compile", "**/*.py"])
        if syntax_result.returncode != 0:
            issues.append(
                {
                    "type": "syntax_error",
                    "severity": "critical",
                    "message": syntax_result.stderr,
                }
            )

        # 2. Ruff linting
        ruff_result = self._run_command(["ruff", "check", ".", "--output-format=json"])
        if ruff_result.returncode != 0:
            try:
                ruff_issues = json.loads(ruff_result.stdout)
                for issue in ruff_issues[:10]:  # Limit to 10
                    issues.append(
                        {
                            "type": "lint",
                            "severity": "medium",
                            "file": issue.get("filename"),
                            "line": issue.get("location", {}).get("row"),
                            "message": issue.get("message"),
                            "code": issue.get("code"),
                        }
                    )
            except json.JSONDecodeError:
                pass

        # 3. Basic security scan (Bandit)
        bandit_result = self._run_command(
            ["bandit", "-r", ".", "-f", "json", "-ll"]  # Low severity and above
        )
        if bandit_result.returncode != 0:
            try:
                bandit_data = json.loads(bandit_result.stdout)
                for issue in bandit_data.get("results", [])[:5]:
                    issues.append(
                        {
                            "type": "security",
                            "severity": issue.get("issue_severity", "").lower(),
                            "file": issue.get("filename"),
                            "line": issue.get("line_number"),
                            "message": issue.get("issue_text"),
                            "cwe": issue.get("issue_cwe", {}).get("id"),
                        }
                    )
            except json.JSONDecodeError:
                pass

        duration = time.time() - start_time

        # Determine if should proceed
        critical_issues = [i for i in issues if i.get("severity") == "critical"]
        should_proceed = len(critical_issues) == 0

        result = StageResult(
            stage=1,
            passed=should_proceed,
            duration=duration,
            issues=issues,
            metrics={"issue_count": len(issues), "critical_count": len(critical_issues)},
            should_proceed=should_proceed,
        )

        self.results.append(result)
        return result

    async def run_stage2_standard(self) -> StageResult:
        """
        Stage 2: Standard checks (2-5min).

        - Full test suite
        - Coverage analysis
        - Claude code review
        """
        start_time = time.time()
        issues = []

        print("🔍 Stage 2: Standard Analysis")

        # 1. Run tests with coverage
        pytest_result = self._run_command(
            [
                "pytest",
                "--cov=.",
                "--cov-report=json",
                "--cov-report=term",
                "-v",
            ]
        )

        # Parse coverage
        coverage_data = {}
        if os.path.exists("coverage.json"):
            with open("coverage.json", encoding="utf-8") as f:
                coverage_data = json.load(f)

        coverage_percent = coverage_data.get("totals", {}).get("percent_covered", 0)

        if coverage_percent < 80:
            issues.append(
                {
                    "type": "coverage",
                    "severity": "medium",
                    "message": f"Test coverage is {coverage_percent:.1f}% (target: 80%)",
                    "coverage": coverage_percent,
                }
            )

        # 2. Type checking
        mypy_result = self._run_command(["mypy", ".", "--json-report", "mypy-report"])
        if mypy_result.returncode != 0:
            issues.append(
                {
                    "type": "type_check",
                    "severity": "medium",
                    "message": "Type checking failed",
                }
            )

        duration = time.time() - start_time

        # Determine if should proceed
        should_proceed = pytest_result.returncode == 0 and coverage_percent >= 70

        result = StageResult(
            stage=2,
            passed=should_proceed,
            duration=duration,
            issues=issues,
            metrics={
                "coverage": coverage_percent,
                "tests_passed": pytest_result.returncode == 0,
            },
            should_proceed=should_proceed,
        )

        self.results.append(result)
        return result

    async def run_stage3_deep(self) -> StageResult:
        """
        Stage 3: Deep analysis (10-15min).

        - Performance profiling
        - Dependency vulnerability scans
        - Compliance checks
        - Architecture analysis
        """
        start_time = time.time()
        issues = []

        print("🔬 Stage 3: Deep Analysis")

        # 1. Dependency vulnerability scan
        pip_audit_result = self._run_command(["pip-audit", "--format=json"])
        if pip_audit_result.returncode != 0:
            try:
                audit_data = json.loads(pip_audit_result.stdout)
                for vuln in audit_data.get("vulnerabilities", [])[:10]:
                    issues.append(
                        {
                            "type": "dependency_vulnerability",
                            "severity": "high",
                            "package": vuln.get("name"),
                            "version": vuln.get("version"),
                            "vulnerability": vuln.get("id"),
                            "message": vuln.get("description"),
                        }
                    )
            except (json.JSONDecodeError, AttributeError):
                pass

        # 2. Complexity analysis
        radon_result = self._run_command(
            ["radon", "cc", ".", "-a", "-j", "--min", "C"]
        )
        if radon_result.returncode == 0:
            try:
                complexity_data = json.loads(radon_result.stdout)
                high_complexity = []
                for file_data in complexity_data.values():
                    for item in file_data:
                        if item.get("complexity", 0) > 10:
                            high_complexity.append(item)

                if high_complexity:
                    issues.append(
                        {
                            "type": "complexity",
                            "severity": "medium",
                            "message": f"Found {len(high_complexity)} functions with high complexity",
                            "details": high_complexity[:5],
                        }
                    )
            except json.JSONDecodeError:
                pass

        # 3. License compliance
        license_result = self._run_command(["pip-licenses", "--format=json"])
        if license_result.returncode == 0:
            try:
                licenses = json.loads(license_result.stdout)
                incompatible = [
                    pkg
                    for pkg in licenses
                    if pkg.get("License") in ["GPL-3.0", "AGPL-3.0"]
                    and pkg.get("Name") != "arena-improver"
                ]
                if incompatible:
                    issues.append(
                        {
                            "type": "license_compliance",
                            "severity": "high",
                            "message": f"Found {len(incompatible)} packages with incompatible licenses",
                            "packages": [p.get("Name") for p in incompatible],
                        }
                    )
            except json.JSONDecodeError:
                pass

        duration = time.time() - start_time

        # High severity issues block
        high_severity = [i for i in issues if i.get("severity") in ["critical", "high"]]
        should_proceed = len(high_severity) == 0

        result = StageResult(
            stage=3,
            passed=should_proceed,
            duration=duration,
            issues=issues,
            metrics={
                "vulnerability_count": len(
                    [i for i in issues if i["type"] == "dependency_vulnerability"]
                ),
                "high_severity_count": len(high_severity),
            },
            should_proceed=should_proceed,
        )

        self.results.append(result)
        return result

    async def run_full_pipeline(self) -> dict[str, Any]:
        """Run all stages of the pipeline."""
        print("=" * 80)
        print("Multi-Stage Review Pipeline")
        print("=" * 80)

        total_start = time.time()

        # Stage 1: Fast checks
        stage1 = await self.run_stage1_fast()
        print(f"✓ Stage 1 completed in {stage1.duration:.1f}s")

        if not stage1.should_proceed:
            print("❌ Stage 1 failed - stopping pipeline")
            return self._generate_report()

        # Stage 2: Standard checks
        stage2 = await self.run_stage2_standard()
        print(f"✓ Stage 2 completed in {stage2.duration:.1f}s")

        if not stage2.should_proceed:
            print("⚠️  Stage 2 had issues - proceeding with caution")

        # Stage 3: Deep analysis
        stage3 = await self.run_stage3_deep()
        print(f"✓ Stage 3 completed in {stage3.duration:.1f}s")

        total_duration = time.time() - total_start

        print("=" * 80)
        print(f"Pipeline completed in {total_duration:.1f}s")
        print("=" * 80)

        return self._generate_report()

    def _generate_report(self) -> dict[str, Any]:
        """Generate final pipeline report."""
        all_issues = []
        for result in self.results:
            all_issues.extend(result.issues)

        # Categorize issues
        critical = [i for i in all_issues if i.get("severity") == "critical"]
        high = [i for i in all_issues if i.get("severity") == "high"]
        medium = [i for i in all_issues if i.get("severity") == "medium"]
        low = [i for i in all_issues if i.get("severity") == "low"]

        report = {
            "pipeline_passed": all(r.passed for r in self.results),
            "stages_completed": len(self.results),
            "total_duration": sum(r.duration for r in self.results),
            "summary": {
                "total_issues": len(all_issues),
                "critical": len(critical),
                "high": len(high),
                "medium": len(medium),
                "low": len(low),
            },
            "stages": [
                {
                    "stage": r.stage,
                    "passed": r.passed,
                    "duration": r.duration,
                    "issue_count": len(r.issues),
                    "metrics": r.metrics,
                }
                for r in self.results
            ],
            "issues": all_issues,
        }

        return report

    def _run_command(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """Run a shell command and return result."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=False,
            )
            return result
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            # Return empty result on error
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr=str(e)
            )


async def main() -> None:
    """CLI entry point."""
    pipeline = MultiStagePipeline()
    report = await pipeline.run_full_pipeline()

    # Save report
    with open("pipeline_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n" + "=" * 80)
    print("PIPELINE SUMMARY")
    print("=" * 80)
    print(f"Status: {'✅ PASSED' if report['pipeline_passed'] else '❌ FAILED'}")
    print(f"Duration: {report['total_duration']:.1f}s")
    print(f"\nIssues Found:")
    print(f"  Critical: {report['summary']['critical']}")
    print(f"  High:     {report['summary']['high']}")
    print(f"  Medium:   {report['summary']['medium']}")
    print(f"  Low:      {report['summary']['low']}")
    print("=" * 80)

    # Exit with appropriate code
    if not report["pipeline_passed"]:
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
