"""Phase 10.9 ranking hardening version identifier."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

RANKING_HARDENING_VERSION = "10.9.0"
RANKING_FAILURE_ANALYSIS_VERSION = "10.9.0"


class ExperimentalLTRRankingConfig(BaseModel):
    """Explicit opt-in LTR settings (never used by ``retrieve_ranked`` by default)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(
        default=False,
        description="When true, offline helpers may load LTR; production retrieve_ranked stays baseline.",
    )
    artifact_directory: str | None = Field(
        default=None,
        description="Filesystem path to Phase 10.7 artifact directory.",
    )

    @model_validator(mode="after")
    def enabled_requires_artifact_path(self) -> ExperimentalLTRRankingConfig:
        if self.enabled and (not self.artifact_directory or not self.artifact_directory.strip()):
            msg = "experimental LTR requires artifact_directory when enabled"
            raise ValueError(msg)
        return self


__all__ = [
    "RANKING_FAILURE_ANALYSIS_VERSION",
    "RANKING_HARDENING_VERSION",
    "ExperimentalLTRRankingConfig",
]
