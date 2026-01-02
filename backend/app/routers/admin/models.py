"""
Admin Panel Shared Models
=========================

Shared base models and utilities for admin panel endpoints.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """
    Base model that serializes to camelCase for frontend compatibility.
    
    All admin response models should inherit from this class to ensure
    consistent JSON field naming between backend (snake_case) and 
    frontend (camelCase).
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        serialize_by_alias=True,  # Critical: ensures JSON output uses camelCase
    )

