"""Base classes shared by all source adapters."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session


@dataclass
class RawListing:
    title: str
    url: str
    raw_text: str
    source_name: str
    source_type: str  # API / RSS / SEARCH / FETCH
    extra: dict = field(default_factory=dict)


class SourceAdapter(Protocol):
    name: str
    kind: str  # API / RSS / SEARCH

    def fetch(self, db: Session, query: str, limit: int = 20) -> list[RawListing]:
        """Fetch raw listings for a search query."""
        ...
