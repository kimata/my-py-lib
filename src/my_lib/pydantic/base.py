#!/usr/bin/env python3
"""Base classes for Pydantic models."""

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """All Pydantic models base class."""

    model_config = ConfigDict(
        from_attributes=True,  # dataclass conversion support
        strict=False,
        extra="ignore",  # for gradual migration
        use_enum_values=True,
    )
