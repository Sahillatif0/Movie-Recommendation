"""Simple recommendation routines over the built graph.

Provides a lightweight heuristic recommender that works off the
user-item bipartite graph without requiring a full ML pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple


def _paths():
	root = Path(__file__).resolve().parent.parent
	results = root / "results"
	results.mkdir(parents=True, exist_ok=True)
	graph_path = results / "user_item_graph.gpickle"
	return root, results, graph_path


def _load_graph_or_build():
	from importlib import import_module
	import networkx as nx

	root, results, graph_path = _paths()
	if not graph_path.exists():
		# Build if missing
		build_graph = import_module("src.build_graph") if (root / "src").exists() else import_module("build_graph")
		build_graph.main()
	return nx.read_gpickle(graph_path)


def _user_node(user_id: int) -> str:
	return f"user_{int(user_id)}"


def _is_item(node: str, data: dict) -> bool:
	bt = data.get("bipartite")
	return bt == "item" or (isinstance(node, str) and node.startswith("item_"))


def _neighbors(G, n):
	return set(G.neighbors(n)) if G.has_node(n) else set()


def recommend_for_user(user_id: int, top_k: int = 10) -> List[Tuple[str, float]]:
	"""Recommend items via a simple 2-hop co-occurrence score.

	For each candidate item not already interacted by the user, score it by the
	number of 2-hop paths user->other_user->candidate_item. This is a common
	baseline for bipartite recommenders and works even on small graphs.
	"""
	import networkx as nx  # noqa: F401 (lazy import)

	G = _load_graph_or_build()
	u = _user_node(user_id)
	if not G.has_node(u):
		return []

	# Items the user already has
	user_items = {v for v in _neighbors(G, u) if G.nodes[v].get("bipartite") == "item"}

	# All items in graph
	all_items = {n for n, d in G.nodes(data=True) if _is_item(n, d)}
	candidates = all_items - user_items

	# Users who interacted with user's items (2-hop middle nodes)
	two_hop_users = set()
	for it in user_items:
		two_hop_users |= _neighbors(G, it)
	two_hop_users.discard(u)

	if not candidates:
		return []

	scores = {}
	for it in candidates:
		# Count how many 2-hop users also interacted with candidate item
		count = 0
		neigh = _neighbors(G, it)
		if two_hop_users and neigh:
			count = len(two_hop_users & neigh)
		scores[it] = float(count)

	ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
	return ranked[:top_k]


def save_recommendations(user_id: int, recs: List[Tuple[str, float]]):
	import csv
	_, results, _ = _paths()
	out = results / "recommendation_samples.csv"
	out.parent.mkdir(parents=True, exist_ok=True)
	with out.open("w", newline="", encoding="utf-8") as f:
		w = csv.writer(f)
		w.writerow(["rank", "item_node", "score"])
		for idx, (item, score) in enumerate(recs, start=1):
			w.writerow([idx, item, f"{score:.6f}"])
	return out


def main():
	import argparse

	p = argparse.ArgumentParser(description="Generate simple recommendations for a user")
	p.add_argument("--user", type=int, default=1, help="User ID to recommend for (default: 1)")
	p.add_argument("--topk", type=int, default=10, help="Number of items to recommend (default: 10)")
	args = p.parse_args()

	recs = recommend_for_user(args.user, args.topk)
	out = save_recommendations(args.user, recs)
	print(f"Wrote {len(recs)} recommendations for user {args.user} to {out}")


if __name__ == "__main__":
	main()

