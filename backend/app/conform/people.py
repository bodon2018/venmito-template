"""Merge the two people sources into one conformed set.

Order matters: the sources are compared BEFORE they are coalesced, so a
disagreement is reported rather than silently resolved by precedence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .normalize import (DEVICES, normalize_email, normalize_phone, parse_dob,
                        parse_id, split_city, split_name)

VALUE_FIELDS = ("first_name", "last_name", "email", "phone", "city", "country", "dob")


@dataclass
class ConformedPeople:
    people: dict[int, dict[str, Any]] = field(default_factory=dict)
    devices: dict[int, set[str]] = field(default_factory=dict)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    sources: dict[int, set[str]] = field(default_factory=dict)


def normalize_person(record: dict[str, Any], origin: str) -> dict[str, Any]:
    """Turn either source's record shape into the one canonical shape."""
    if "name" in record:                              # yaml shape
        first, last = split_name(record.get("name") or "")
        city, country = split_city(record.get("city_country") or "")
    else:                                             # json shape
        first = (record.get("first_name") or "").strip()
        last = (record.get("last_name") or "").strip()
        city = (record.get("city") or "").strip()
        country = (record.get("country") or "").strip()

    return {
        "id": parse_id(record["id"]),
        "first_name": first,
        "last_name": last,
        "email": normalize_email(record.get("email")),
        "phone": normalize_phone(record.get("phone")),
        "city": city,
        "country": country,
        "dob": parse_dob(record.get("dob")),
        "devices": {d for d in (record.get("devices") or []) if d in DEVICES},
        "source": origin,
    }


def merge_people(batches: list[tuple[str, list[dict[str, Any]]]],
                 precedence: tuple[str, ...] = ()) -> ConformedPeople:
    """Outer-join every people source on id.

    An outer join is the point: the sources partition the population by
    geography, so taking either one alone drops whole countries.

    `precedence` lists source names best-first. It only has an effect on ids
    where the sources actually disagree -- every such id is recorded in
    `conflicts` regardless.
    """
    out = ConformedPeople()
    rank = {name: i for i, name in enumerate(precedence)}

    for origin, records in batches:
        for record in records:
            person = normalize_person(record, origin)
            pid = person["id"]
            out.sources.setdefault(pid, set()).add(origin)
            existing = out.people.get(pid)

            if existing is None:
                out.people[pid] = person
                out.devices[pid] = person["devices"]
                continue

            differing = {f: (existing[f], person[f])
                         for f in VALUE_FIELDS if existing[f] != person[f]}
            if differing:
                out.conflicts.append({
                    "id": pid,
                    "kept_source": existing["source"],
                    "other_source": origin,
                    "fields": differing,
                })
                # Lower rank wins; unknown sources never displace a known one.
                if rank.get(origin, len(rank)) < rank.get(existing["source"], len(rank)):
                    out.people[pid] = person
                    out.devices[pid] = person["devices"]
            else:
                out.devices[pid] |= person["devices"]

    for pid, person in out.people.items():
        person["devices"] = out.devices.get(pid, set())
        person["source"] = "+".join(sorted(out.sources[pid]))
    return out
