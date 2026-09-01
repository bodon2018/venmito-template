"""Analysis over the conformed data.

Read-only. Nothing here writes, so it can be called on any request without
side effects. Each function returns plain dicts and lists, ready to serialise.
"""
from .service import build_report, section

__all__ = ["build_report", "section"]
