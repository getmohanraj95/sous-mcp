"""Session-scoped pantry and dietary-profile storage."""
from __future__ import annotations

from .matching import normalize
from .models import DietaryProfile, normalize_names


class PantryStore:
    """In-memory pantry state keyed by MCP session.

    The only class that knows about storage. Replace the dicts with Redis or
    DynamoDB for production; the public methods are the whole contract.
    """

    def __init__(self) -> None:
        self._pantries: dict[str, dict[str, str]] = {}
        self._profiles: dict[str, DietaryProfile] = {}

    def items(self, session_id: str) -> list[str]:
        return list(self._pantries.get(session_id, {}).values())

    def add(self, session_id: str, names: list[str]) -> list[str]:
        """Add items; returns the names that were newly added."""
        bucket = self._pantries.setdefault(session_id, {})
        added: list[str] = []
        for name in normalize_names(names):
            key = normalize(name)
            if key not in bucket:
                bucket[key] = name
                added.append(name)
        return added

    def remove(self, session_id: str, names: list[str]) -> list[str]:
        """Remove items; returns the names that were actually removed."""
        bucket = self._pantries.get(session_id, {})
        removed: list[str] = []
        for name in normalize_names(names):
            if bucket.pop(normalize(name), None) is not None:
                removed.append(name)
        return removed

    def profile(self, session_id: str) -> DietaryProfile:
        return self._profiles.setdefault(session_id, DietaryProfile())

    def update_profile(
        self,
        session_id: str,
        restrictions: list[str] | None = None,
        allergies: list[str] | None = None,
    ) -> DietaryProfile:
        """Replace whichever lists are provided; leave the others unchanged."""
        profile = self.profile(session_id)
        if restrictions is not None:
            profile.restrictions = normalize_names(restrictions)
        if allergies is not None:
            profile.allergies = normalize_names(allergies)
        return profile
