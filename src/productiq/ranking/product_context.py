"""Product context supplied to ranking feature extraction (Phase 10.2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.schema import ProductRepresentation


class RankingProductContext(BaseModel):
    """Catalog representation for one candidate (injected; no database loading)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    product: ProductRepresentation
    filtering: FilteringRepresentation | None = None

    @model_validator(mode="after")
    def validate_product_id_alignment(self) -> RankingProductContext:
        if self.product_id != self.product.product_id:
            msg = "RankingProductContext.product_id must match product.product_id"
            raise ValueError(msg)
        if self.filtering is not None and self.filtering.product_id != self.product_id:
            msg = "filtering.product_id must match RankingProductContext.product_id"
            raise ValueError(msg)
        return self


__all__ = ["RankingProductContext"]
