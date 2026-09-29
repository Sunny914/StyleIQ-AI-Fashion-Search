"""Validation result models for data quality checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ValidationStatus(StrEnum):
    """Outcome of an individual validation check."""

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class ValidationSeverity(StrEnum):
    """Severity associated with a validation finding."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ValidationFinding:
    """Single validation check result."""

    category: str
    rule_name: str
    status: ValidationStatus
    severity: ValidationSeverity
    message: str
    affected_row_count: int | None = None


@dataclass
class ValidationReport:
    """Collection of validation findings for one dataset validation run."""

    findings: list[ValidationFinding] = field(default_factory=list)

    def add(self, finding: ValidationFinding) -> None:
        """Append a finding to the report."""
        self.findings.append(finding)

    @property
    def has_failures(self) -> bool:
        """Return whether any finding failed validation."""
        return any(finding.status is ValidationStatus.FAIL for finding in self.findings)

    @property
    def has_warnings(self) -> bool:
        """Return whether any finding produced a warning."""
        return any(finding.status is ValidationStatus.WARNING for finding in self.findings)

    def summary(self) -> str:
        """Return a human-readable grouped summary."""
        if not self.findings:
            return "No validation findings recorded."

        lines: list[str] = []
        current_category: str | None = None

        for finding in self.findings:
            if finding.category != current_category:
                current_category = finding.category
                lines.append(current_category)

            if finding.status is ValidationStatus.PASS:
                lines.append("  PASS")
                continue

            detail = f"  {finding.status.value}: {finding.message}"
            if finding.affected_row_count is not None:
                detail = f"{detail} ({finding.affected_row_count} rows)"
            lines.append(detail)

        return "\n".join(lines)

    def findings_by_category(self, category: str) -> list[ValidationFinding]:
        """Return findings for a specific category."""
        return [finding for finding in self.findings if finding.category == category]
