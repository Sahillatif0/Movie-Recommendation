"""Utility functions for the Movie Recommendation system.

Currently lightweight; expands as functionality grows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Dict, Any


@dataclass(frozen=True)
class Rating:
	user_id: int
	item_id: int
	rating: float


def parse_ratings(lines: Iterable[str], sep: str = "\t") -> List[Rating]:
	"""Parse raw rating lines into Rating objects.

	Expected format per line: user_id<sep>item_id<sep>rating
	Skips malformed lines.

	Args:
		lines: Iterable of raw lines.
		sep: Field separator (default: tab for common MovieLens variants).
	Returns:
		List of Rating objects.
	"""
	parsed: List[Rating] = []
	for ln in lines:
		ln = ln.strip()
		if not ln:
			continue
		parts = ln.split(sep)
		if len(parts) < 3:
			continue
		try:
			u, i, r = int(parts[0]), int(parts[1]), float(parts[2])
		except ValueError:
			continue
		parsed.append(Rating(u, i, r))
	return parsed


def top_n(scores: Dict[Any, float], n: int) -> List[Any]:
	"""Return the top-n keys from a score mapping ordered by descending score.

	Args:
		scores: Mapping of key -> score.
		n: Number of top items to return.
	Returns:
		List of keys (may be fewer than n if insufficient elements).
	"""
	return [k for k, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:n]]


__all__ = ["Rating", "parse_ratings", "top_n"]

