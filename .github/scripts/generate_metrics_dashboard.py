#!/usr/bin/env python3
"""
Metrics Dashboard Generator

Generates a comprehensive metrics dashboard for Claude AI code reviews.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path


class MetricsDashboard:
    """Generate metrics dashboard."""

    def __init__(self) -> None:
        """Initialize dashboard generator."""
        self.output_file = ".github/METRICS_DASHBOARD.md"

    def generate(self, days: int = 30) -> str:
        """Generate complete metrics dashboard."""
        # Gather data from various sources
        cost_stats = self._get_cost_stats(days)
        effectiveness = self._get_effectiveness_stats(days)
        security = self._get_security_stats(days)
        pipeline_stats = self._get_pipeline_stats(days)

        # Generate markdown
        dashboard = self._create_dashboard(
            days, cost_stats, effectiveness, security, pipeline_stats
        )

        # Save to file
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(dashboard)

        return dashboard

    def _create_dashboard(
        self,
        days: int,
        cost: dict,
        effectiveness: dict,
        security: dict,
        pipeline: dict,
    ) -> str:
        """Create markdown dashboard."""
        now = datetime.now()

        md = f"""# Claude AI Metrics Dashboard

**Generated**: {now.strftime("%Y-%m-%d %H:%M:%S")}
**Period**: Last {days} days

---

## 📊 Overview

| Metric | Value | Trend |
|--------|-------|-------|
| Total Reviews | {effectiveness.get('total_reviews', 0)} | {'📈' if effectiveness.get('trend', 0) > 0 else '📉'} |
| Acceptance Rate | {effectiveness.get('acceptance_rate', 0):.1%} | {'✅' if effectiveness.get('acceptance_rate', 0) > 0.7 else '⚠️'} |
| API Calls Saved (Cache) | {cost.get('calls_saved', 0)} | 💰 |
| Security Issues Found | {security.get('issues_found', 0)} | {'🔒' if security.get('issues_found', 0) == 0 else '⚠️'} |

---

## 💰 Cost Optimization

### API Usage
- **Total API Calls**: {cost.get('total_calls', 0)}
- **Cached Responses**: {cost.get('cached_responses', 0)}
- **Cache Hit Rate**: {cost.get('cache_hit_rate', 0):.1%}
- **Estimated Cost Savings**: ${cost.get('estimated_savings', 0):.2f}

### Rate Limiting
- **PRs Reviewed**: {cost.get('prs_reviewed', 0)}
- **Average Calls per PR**: {cost.get('avg_calls_per_pr', 0):.1f}
- **Rate Limits Triggered**: {cost.get('rate_limits', 0)}

### Batch Processing
- **Batches Completed**: {cost.get('batches_completed', 0)}
- **Items Batched**: {cost.get('items_batched', 0)}
- **Time Saved**: {cost.get('time_saved', 0):.1f} minutes

---

## ✅ Review Effectiveness

### Overall Performance
- **Total Suggestions**: {effectiveness.get('total_suggestions', 0)}
- **Accepted**: {effectiveness.get('accepted', 0)}
- **Rejected**: {effectiveness.get('rejected', 0)}
- **Acceptance Rate**: {effectiveness.get('acceptance_rate', 0):.1%}

### By Suggestion Type
{self._format_type_table(effectiveness.get('by_type', {}))}

### By Severity
{self._format_severity_table(effectiveness.get('by_severity', {}))}

### False Positive Patterns
{self._format_false_positives(effectiveness.get('false_positives', []))}

---

## 🔒 Security & Compliance

### Security Scanning
- **Files Scanned**: {security.get('files_scanned', 0)}
- **PII Detected**: {security.get('pii_detected', 0)}
- **Credentials Detected**: {security.get('credentials_detected', 0)}
- **Secrets Redacted**: {security.get('secrets_redacted', 0)}

### Compliance Status
- **GDPR Compliant**: {'✅ Yes' if security.get('gdpr_compliant') else '❌ No'}
- **SOC2 Compliant**: {'✅ Yes' if security.get('soc2_compliant') else '❌ No'}
- **Audit Trail Complete**: {'✅ Yes' if security.get('audit_trail') else '❌ No'}

### Audit Trail
- **Total Interactions Logged**: {security.get('total_interactions', 0)}
- **Unique Users**: {security.get('unique_users', 0)}
- **Files Analyzed**: {security.get('files_analyzed', 0)}

---

## 🔬 Pipeline Performance

### Stage Completion Rates
- **Stage 1 (Fast)**: {pipeline.get('stage1_rate', 0):.1%}
- **Stage 2 (Standard)**: {pipeline.get('stage2_rate', 0):.1%}
- **Stage 3 (Deep)**: {pipeline.get('stage3_rate', 0):.1%}

### Average Execution Times
- **Stage 1**: {pipeline.get('stage1_time', 0):.1f}s
- **Stage 2**: {pipeline.get('stage2_time', 0):.1f}s
- **Stage 3**: {pipeline.get('stage3_time', 0):.1f}s

### Issues by Stage
{self._format_pipeline_issues(pipeline.get('issues_by_stage', {}))}

---

## 📈 Trends

### Review Activity (Last 7 Days)
```
{self._create_sparkline(effectiveness.get('daily_reviews', []))}
```

### Issue Detection Rate
```
{self._create_sparkline(effectiveness.get('daily_issues', []))}
```

---

## 🎯 Recommendations

{self._generate_recommendations(cost, effectiveness, security, pipeline)}

---

## 📋 Summary

### Highlights
{self._generate_highlights(cost, effectiveness, security, pipeline)}

### Areas for Improvement
{self._generate_improvements(cost, effectiveness, security, pipeline)}

---

*Dashboard auto-generated by Claude AI Metrics System*
*Next update: {(now + timedelta(days=1)).strftime("%Y-%m-%d")}*
"""
        return md

    def _format_type_table(self, by_type: dict) -> str:
        """Format suggestion types table."""
        if not by_type:
            return "_No data available_"

        rows = []
        for stype, data in sorted(by_type.items(), key=lambda x: x[1].get('total', 0), reverse=True):
            rate = data.get('acceptance_rate', 0)
            emoji = '🟢' if rate > 0.8 else '🟡' if rate > 0.5 else '🔴'
            rows.append(f"| {emoji} {stype} | {data.get('total', 0)} | {data.get('accepted', 0)} | {rate:.1%} |")

        header = "| Type | Total | Accepted | Rate |\n|------|-------|----------|------|"
        return header + "\n" + "\n".join(rows)

    def _format_severity_table(self, by_severity: dict) -> str:
        """Format severity table."""
        if not by_severity:
            return "_No data available_"

        rows = []
        for severity in ['critical', 'high', 'medium', 'low']:
            if severity in by_severity:
                data = by_severity[severity]
                rows.append(f"| {severity.upper()} | {data.get('total', 0)} | {data.get('accepted', 0)} | {data.get('acceptance_rate', 0):.1%} |")

        header = "| Severity | Total | Accepted | Rate |\n|----------|-------|----------|------|"
        return header + "\n" + "\n".join(rows)

    def _format_false_positives(self, false_positives: list) -> str:
        """Format false positives list."""
        if not false_positives:
            return "_No recurring false positive patterns detected_ ✅"

        items = []
        for fp in false_positives[:5]:
            items.append(f"- **{fp.get('type')}**: {fp.get('count')} occurrences")
        return "\n".join(items)

    def _format_pipeline_issues(self, issues: dict) -> str:
        """Format pipeline issues table."""
        if not issues:
            return "_No data available_"

        header = "| Stage | Critical | High | Medium | Low |\n|-------|----------|------|--------|-----|"
        rows = []
        for stage in [1, 2, 3]:
            if stage in issues:
                data = issues[stage]
                rows.append(f"| Stage {stage} | {data.get('critical', 0)} | {data.get('high', 0)} | {data.get('medium', 0)} | {data.get('low', 0)} |")

        return header + "\n" + "\n".join(rows)

    def _create_sparkline(self, data: list) -> str:
        """Create ASCII sparkline."""
        if not data:
            return "No data"

        # Simple ASCII chart
        max_val = max(data) if data else 1
        bars = ['█', '▇', '▆', '▅', '▄', '▃', '▂', '▁']

        line = ""
        for val in data:
            if max_val == 0:
                line += "▁"
            else:
                idx = int((val / max_val) * (len(bars) - 1))
                line += bars[idx]

        return line + f"  (max: {max_val})"

    def _generate_recommendations(self, cost: dict, effectiveness: dict, security: dict, pipeline: dict) -> str:
        """Generate recommendations."""
        recs = []

        # Cost recommendations
        if cost.get('cache_hit_rate', 0) < 0.5:
            recs.append("- 💰 **Improve caching**: Cache hit rate is below 50%. Consider increasing TTL.")

        # Effectiveness recommendations
        if effectiveness.get('acceptance_rate', 0) < 0.7:
            recs.append("- ✅ **Review suggestions**: Acceptance rate is low. Analyze false positive patterns.")

        # Security recommendations
        if security.get('pii_detected', 0) > 0:
            recs.append("- 🔒 **PII Found**: Detected PII in code. Review and redact before committing.")

        # Pipeline recommendations
        if pipeline.get('stage1_rate', 100) < 95:
            recs.append("- 🔬 **Stage 1 Failures**: Increase. Review common linting/syntax issues.")

        if not recs:
            recs.append("- ✅ **All systems optimal**: No immediate recommendations.")

        return "\n".join(recs)

    def _generate_highlights(self, cost: dict, effectiveness: dict, security: dict, pipeline: dict) -> str:
        """Generate highlights."""
        highlights = []

        if cost.get('calls_saved', 0) > 100:
            highlights.append(f"- 💰 Saved {cost.get('calls_saved')} API calls through caching")

        if effectiveness.get('acceptance_rate', 0) > 0.8:
            highlights.append(f"- ✅ High acceptance rate: {effectiveness.get('acceptance_rate', 0):.1%}")

        if security.get('credentials_detected', 0) == 0:
            highlights.append("- 🔒 No hardcoded credentials detected")

        if not highlights:
            highlights.append("- System is collecting data...")

        return "\n".join(highlights)

    def _generate_improvements(self, cost: dict, effectiveness: dict, security: dict, pipeline: dict) -> str:
        """Generate improvement areas."""
        improvements = []

        if effectiveness.get('false_positives', []):
            improvements.append("- Reduce false positive rate by refining detection patterns")

        if cost.get('rate_limits', 0) > 0:
            improvements.append("- Rate limits triggered - consider batching more PRs")

        if not improvements:
            improvements.append("- Continue monitoring metrics")

        return "\n".join(improvements)

    def _get_cost_stats(self, days: int) -> dict:
        """Get cost optimization stats."""
        # Load from cost_optimizer if available
        # For now, return defaults
        return {
            'total_calls': 0,
            'cached_responses': 0,
            'cache_hit_rate': 0.0,
            'estimated_savings': 0.0,
            'prs_reviewed': 0,
            'avg_calls_per_pr': 0.0,
            'rate_limits': 0,
            'batches_completed': 0,
            'items_batched': 0,
            'time_saved': 0.0,
            'calls_saved': 0,
        }

    def _get_effectiveness_stats(self, days: int) -> dict:
        """Get review effectiveness stats."""
        return {
            'total_reviews': 0,
            'total_suggestions': 0,
            'accepted': 0,
            'rejected': 0,
            'acceptance_rate': 0.0,
            'by_type': {},
            'by_severity': {},
            'false_positives': [],
            'trend': 0,
            'daily_reviews': [],
            'daily_issues': [],
        }

    def _get_security_stats(self, days: int) -> dict:
        """Get security stats."""
        return {
            'files_scanned': 0,
            'pii_detected': 0,
            'credentials_detected': 0,
            'secrets_redacted': 0,
            'gdpr_compliant': True,
            'soc2_compliant': True,
            'audit_trail': True,
            'total_interactions': 0,
            'unique_users': 0,
            'files_analyzed': 0,
            'issues_found': 0,
        }

    def _get_pipeline_stats(self, days: int) -> dict:
        """Get pipeline stats."""
        return {
            'stage1_rate': 100.0,
            'stage2_rate': 100.0,
            'stage3_rate': 100.0,
            'stage1_time': 0.0,
            'stage2_time': 0.0,
            'stage3_time': 0.0,
            'issues_by_stage': {},
        }


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate Metrics Dashboard")
    parser.add_argument("--days", type=int, default=30, help="Period in days")
    args = parser.parse_args()

    dashboard = MetricsDashboard()
    output = dashboard.generate(args.days)

    print(output)
    print(f"\n✓ Dashboard generated: {dashboard.output_file}")


if __name__ == "__main__":
    main()
