"""Entity resolution and the natural-key lookups everything else joins through.

Two separate problems live here:

  * The same id can mean different people in different files.
  * The same person can hold more than one id, with no shared natural key.

Both are settled by an explicit, configurable policy rather than by whichever
file happened to load last.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .people import ConformedPeople, VALUE_FIELDS


@dataclass
class IdentityResolution:
    canonical: dict[int, int] = field(default_factory=dict)      # id -> surviving id
    synthetic: set[int] = field(default_factory=set)
    stale_ids: dict[int, int] = field(default_factory=dict)      # source-local id -> real id
    email_to_id: dict[str, int] = field(default_factory=dict)
    phone_to_id: dict[str, int] = field(default_factory=dict)
    retired_keys: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def resolve_email(self, value: str | None) -> int | None:
        return self.email_to_id.get((value or "").strip().lower())

    def resolve_phone(self, value: str | None) -> int | None:
        return self.phone_to_id.get((value or "").strip())

    def resolve_person_id(self, value) -> int | None:
        """Map a raw id onto the surviving entity id."""
        try:
            pid = int(value)
        except (TypeError, ValueError):
            return None
        return self.canonical.get(pid, pid)


def resolve_identities(merged: ConformedPeople,
                       duplicate_policy: str = "collapse_to_lowest",
                       synthetic_markers: tuple[str, ...] = ()) -> IdentityResolution:
    """Build the canonical id map and the natural-key lookups.

    duplicate_policy:
      collapse_to_lowest - one entity keeps the lowest id; the other id's
                           email/phone become retired aliases pointing at it.
      quarantine         - both ids are marked synthetic and excluded from
                           client-facing metrics, but are still loaded.
    """
    resolution = IdentityResolution()
    resolution.canonical = {pid: pid for pid in merged.people}

    # A conflicting id means the sources disagree about who that id is.
    for conflict in merged.conflicts:
        resolution.notes.append(
            f"id {conflict['id']}: sources disagree on "
            f"{', '.join(sorted(conflict['fields']))}; kept {conflict['kept_source']}")

    duplicates = _find_duplicate_entities(merged)
    for loser, winner in duplicates.items():
        if duplicate_policy == "collapse_to_lowest":
            resolution.canonical[loser] = winner
            resolution.synthetic.update({loser, winner})
            loser_person = merged.people[loser]
            for key_type, value in (("email", loser_person["email"]),
                                    ("phone", loser_person["phone"])):
                resolution.retired_keys.append(
                    {"person_id": winner, "key_type": key_type, "key_value": value})
            resolution.notes.append(
                f"id {loser} collapsed into {winner} (same person, different keys)")
        elif duplicate_policy == "quarantine":
            resolution.synthetic.update({loser, winner})
            resolution.notes.append(f"ids {winner} and {loser} quarantined as duplicates")
        else:
            raise ValueError(f"unknown duplicate_policy {duplicate_policy!r}")

    for pid, person in merged.people.items():
        if any(marker in person["email"] for marker in synthetic_markers):
            resolution.synthetic.add(pid)

    # Live keys first, then retired aliases -- an alias must win, because the
    # id it points at is the surviving entity.
    for pid, person in merged.people.items():
        target = resolution.canonical[pid]
        resolution.email_to_id.setdefault(person["email"], target)
        resolution.phone_to_id.setdefault(person["phone"], target)
    for alias in resolution.retired_keys:
        lookup = (resolution.email_to_id if alias["key_type"] == "email"
                  else resolution.phone_to_id)
        lookup[alias["key_value"]] = alias["person_id"]

    return resolution


def _find_duplicate_entities(merged: ConformedPeople) -> dict[int, int]:
    """Same human under two ids. Natural keys differ, so match on name + city."""
    by_person: dict[tuple[str, str, str], list[int]] = {}
    for pid, person in merged.people.items():
        key = (person["first_name"].lower(), person["last_name"].lower(), person["city"].lower())
        by_person.setdefault(key, []).append(pid)
    return {max(ids): min(ids) for ids in by_person.values() if len(ids) > 1}
