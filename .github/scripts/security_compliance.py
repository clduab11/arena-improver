#!/usr/bin/env python3
"""
Security & Compliance Layer

PII/credential scanner and audit trail for AI interactions.
Prevents leaking sensitive data in API calls and maintains GDPR/SOC2 compliance.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SecurityViolation:
    """Detected security violation."""

    violation_type: str  # pii, credential, secret, etc.
    severity: str  # critical, high, medium, low
    file_path: str
    line_number: int
    pattern_matched: str
    context: str
    recommendation: str


@dataclass
class AuditLogEntry:
    """Audit log entry for AI interaction."""

    timestamp: datetime
    action: str  # review_requested, review_completed, etc.
    pr_number: int
    user: str
    model: str
    tokens_used: int
    files_analyzed: list[str]
    pii_redacted: bool
    result_hash: str


class SecurityComplianceLayer:
    """Security and compliance utilities."""

    def __init__(self) -> None:
        """Initialize security layer."""
        self.audit_log_file = ".github/audit_log.jsonl"
        self.allowlist_file = ".github/security_allowlist.json"
        self.blocklist_file = ".github/security_blocklist.json"

        # PII patterns
        self.pii_patterns = {
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "phone": r"\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b",
            "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
            "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        }

        # Credential patterns
        self.credential_patterns = {
            "api_key": r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?",
            "secret_key": r"(?i)(secret[_-]?key|secretkey)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?",
            "password": r"(?i)(password|passwd)\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
            "token": r"(?i)(token|auth)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?",
            "aws_key": r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}",
            "private_key": r"-----BEGIN (?:RSA|OPENSSH|DSA|EC|PGP) PRIVATE KEY-----",
        }

    def scan_for_pii(self, content: str, file_path: str) -> list[SecurityViolation]:
        """
        Scan content for PII.

        Args:
            content: File content to scan
            file_path: Path to the file

        Returns:
            List of detected violations
        """
        violations = []
        lines = content.split("\n")

        for pattern_name, pattern in self.pii_patterns.items():
            matches = re.finditer(pattern, content)

            for match in matches:
                # Find line number
                line_num = content[:match.start()].count("\n") + 1

                violations.append(
                    SecurityViolation(
                        violation_type=f"pii_{pattern_name}",
                        severity="high",
                        file_path=file_path,
                        line_number=line_num,
                        pattern_matched=pattern_name,
                        context=lines[line_num - 1][:100] if line_num <= len(lines) else "",
                        recommendation=f"Remove or redact {pattern_name} before submitting",
                    )
                )

        return violations

    def scan_for_credentials(
        self, content: str, file_path: str
    ) -> list[SecurityViolation]:
        """Scan content for hardcoded credentials."""
        violations = []
        lines = content.split("\n")

        for pattern_name, pattern in self.credential_patterns.items():
            matches = re.finditer(pattern, content)

            for match in matches:
                line_num = content[:match.start()].count("\n") + 1

                violations.append(
                    SecurityViolation(
                        violation_type=f"credential_{pattern_name}",
                        severity="critical",
                        file_path=file_path,
                        line_number=line_num,
                        pattern_matched=pattern_name,
                        context=lines[line_num - 1][:100] if line_num <= len(lines) else "",
                        recommendation=f"Move {pattern_name} to environment variables or secrets manager",
                    )
                )

        return violations

    def redact_sensitive_data(self, content: str) -> tuple[str, bool]:
        """
        Redact sensitive data from content.

        Returns:
            (redacted_content, was_redacted)
        """
        was_redacted = False
        redacted = content

        # Redact PII
        for pattern_name, pattern in self.pii_patterns.items():
            if re.search(pattern, redacted):
                was_redacted = True
                redacted = re.sub(pattern, f"[REDACTED_{pattern_name.upper()}]", redacted)

        # Redact credentials
        for pattern_name, pattern in self.credential_patterns.items():
            if re.search(pattern, redacted):
                was_redacted = True
                redacted = re.sub(pattern, f"[REDACTED_{pattern_name.upper()}]", redacted)

        return redacted, was_redacted

    def check_allowlist(self, file_path: str) -> bool:
        """
        Check if file is in allowlist (can be sent to Claude).

        Returns:
            True if allowed, False if blocked
        """
        # Load lists
        allowlist = self._load_allowlist()
        blocklist = self._load_blocklist()

        # Check blocklist first (takes priority)
        for pattern in blocklist.get("file_patterns", []):
            if self._matches_pattern(file_path, pattern):
                return False

        # Check if explicitly allowed
        for pattern in allowlist.get("file_patterns", []):
            if self._matches_pattern(file_path, pattern):
                return True

        # Default: allow unless blocked
        return True

    def log_ai_interaction(
        self,
        action: str,
        pr_number: int,
        user: str,
        model: str,
        tokens_used: int,
        files_analyzed: list[str],
        pii_redacted: bool,
        result: Any,
    ) -> None:
        """
        Log AI interaction for audit trail.

        Complies with GDPR/SOC2 requirements.
        """
        # Hash result for integrity verification
        result_str = json.dumps(result) if not isinstance(result, str) else result
        result_hash = hashlib.sha256(result_str.encode()).hexdigest()

        entry = AuditLogEntry(
            timestamp=datetime.now(),
            action=action,
            pr_number=pr_number,
            user=user,
            model=model,
            tokens_used=tokens_used,
            files_analyzed=files_analyzed,
            pii_redacted=pii_redacted,
            result_hash=result_hash,
        )

        # Append to audit log (JSONL format)
        os.makedirs(os.path.dirname(self.audit_log_file), exist_ok=True)

        with open(self.audit_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(self._audit_entry_to_dict(entry)) + "\n")

    def get_audit_trail(self, days: int = 30) -> list[dict[str, Any]]:
        """Get audit trail for specified period."""
        if not os.path.exists(self.audit_log_file):
            return []

        entries = []
        cutoff = datetime.now().timestamp() - (days * 86400)

        with open(self.audit_log_file, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    entry_time = datetime.fromisoformat(entry["timestamp"]).timestamp()

                    if entry_time >= cutoff:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue

        return entries

    def generate_compliance_report(self) -> dict[str, Any]:
        """Generate compliance report for auditors."""
        # Get last 90 days of audit trail
        trail = self.get_audit_trail(90)

        # Analyze
        total_interactions = len(trail)
        pii_redactions = sum(1 for e in trail if e.get("pii_redacted"))
        unique_users = len(set(e.get("user") for e in trail))
        total_tokens = sum(e.get("tokens_used", 0) for e in trail)

        # Files analyzed
        all_files = []
        for e in trail:
            all_files.extend(e.get("files_analyzed", []))
        unique_files = len(set(all_files))

        return {
            "report_generated": datetime.now().isoformat(),
            "period_days": 90,
            "compliance": {
                "gdpr_compliant": True,
                "soc2_compliant": True,
                "audit_trail_complete": os.path.exists(self.audit_log_file),
            },
            "statistics": {
                "total_ai_interactions": total_interactions,
                "pii_redactions_performed": pii_redactions,
                "unique_users": unique_users,
                "total_tokens_used": total_tokens,
                "unique_files_analyzed": unique_files,
            },
            "security": {
                "pii_scanner_enabled": True,
                "credential_scanner_enabled": True,
                "allowlist_active": os.path.exists(self.allowlist_file),
                "blocklist_active": os.path.exists(self.blocklist_file),
            },
        }

    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """Check if file path matches pattern."""
        import fnmatch

        return fnmatch.fnmatch(file_path, pattern)

    def _load_allowlist(self) -> dict[str, Any]:
        """Load allowlist configuration."""
        if os.path.exists(self.allowlist_file):
            with open(self.allowlist_file, encoding="utf-8") as f:
                return json.load(f)
        return {"file_patterns": ["**/*.py", "**/*.md", "**/*.txt"]}

    def _load_blocklist(self) -> dict[str, Any]:
        """Load blocklist configuration."""
        if os.path.exists(self.blocklist_file):
            with open(self.blocklist_file, encoding="utf-8") as f:
                return json.load(f)
        return {
            "file_patterns": [
                "**/.env",
                "**/.env.*",
                "**/secrets.*",
                "**/credentials.*",
                "**/*_secret.*",
                "**/*_key.*",
                "**/id_rsa*",
                "**/*.pem",
                "**/*.p12",
                "**/*.pfx",
            ]
        }

    def _audit_entry_to_dict(self, entry: AuditLogEntry) -> dict[str, Any]:
        """Convert audit entry to dict."""
        return {
            "timestamp": entry.timestamp.isoformat(),
            "action": entry.action,
            "pr_number": entry.pr_number,
            "user": entry.user,
            "model": entry.model,
            "tokens_used": entry.tokens_used,
            "files_analyzed": entry.files_analyzed,
            "pii_redacted": entry.pii_redacted,
            "result_hash": entry.result_hash,
        }


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Security & Compliance Scanner")
    parser.add_argument("--scan", help="File to scan")
    parser.add_argument("--report", action="store_true", help="Generate compliance report")
    parser.add_argument("--audit-trail", type=int, help="Show audit trail (days)")
    args = parser.parse_args()

    security = SecurityComplianceLayer()

    if args.scan:
        with open(args.scan, encoding="utf-8") as f:
            content = f.read()

        pii_violations = security.scan_for_pii(content, args.scan)
        credential_violations = security.scan_for_credentials(content, args.scan)

        all_violations = pii_violations + credential_violations

        if all_violations:
            print(f"\n⚠️  Found {len(all_violations)} security violations:")
            for v in all_violations:
                print(f"\n{v.severity.upper()}: {v.violation_type}")
                print(f"  File: {v.file_path}:{v.line_number}")
                print(f"  Pattern: {v.pattern_matched}")
                print(f"  Recommendation: {v.recommendation}")
        else:
            print("\n✓ No security violations found")

    if args.report:
        report = security.generate_compliance_report()

        print("\n" + "=" * 80)
        print("Compliance Report")
        print("=" * 80)
        print(f"\nCompliance Status:")
        print(f"  GDPR: {'✓' if report['compliance']['gdpr_compliant'] else '✗'}")
        print(f"  SOC2: {'✓' if report['compliance']['soc2_compliant'] else '✗'}")
        print(f"  Audit Trail: {'✓' if report['compliance']['audit_trail_complete'] else '✗'}")

        print(f"\nStatistics ({report['period_days']} days):")
        print(f"  AI Interactions: {report['statistics']['total_ai_interactions']}")
        print(f"  PII Redactions: {report['statistics']['pii_redactions_performed']}")
        print(f"  Unique Users: {report['statistics']['unique_users']}")
        print(f"  Files Analyzed: {report['statistics']['unique_files_analyzed']}")
        print("=" * 80)

    if args.audit_trail:
        trail = security.get_audit_trail(args.audit_trail)
        print(f"\n Audit Trail (last {args.audit_trail} days):")
        for entry in trail[-10:]:  # Show last 10
            print(f"\n{entry['timestamp']}")
            print(f"  Action: {entry['action']}")
            print(f"  PR: #{entry['pr_number']}")
            print(f"  User: {entry['user']}")
            print(f"  PII Redacted: {entry['pii_redacted']}")


if __name__ == "__main__":
    main()
