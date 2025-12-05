"""Evaluation utilities for recommendation quality.

Currently implements a tiny placeholder metric (coverage) and structure
for future expansion to precision@k, recall@k, MAP, NDCG, etc.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Iterable


def coverage(recommended: Iterable[str], all_items: Iterable[str]) -> float:
	"""Fraction of total items that appear at least once in recommendations."""
	rec_set = set(recommended)
	item_set = set(all_items)
	if not item_set:
		return 0.0
	return len(rec_set & item_set) / len(item_set)


def _paths():
	root = Path(__file__).resolve().parent.parent
	results = root / "results"
	results.mkdir(parents=True, exist_ok=True)
	return root, results


def evaluate_sample():
	"""Evaluate the current recommendation_samples.csv file if present."""
	import csv
	root, results = _paths()
	rec_file = results / "recommendation_samples.csv"
	graph_file = results / "user_item_graph.gpickle"

	if not rec_file.exists() or rec_file.stat().st_size == 0:
		return {"coverage": 0.0, "notes": "No recommendations present"}

	# Items recommended
	rec_items: List[str] = []
	with rec_file.open("r", encoding="utf-8") as f:
		r = csv.DictReader(f)
		for row in r:
			rec_items.append(row["item_node"])

	# Load graph for set of all items
	try:
		import networkx as nx
		if graph_file.exists():
			G = nx.read_gpickle(graph_file)
			all_graph_items = [n for n, d in G.nodes(data=True) if d.get("bipartite") == "item"]
		else:
			all_graph_items = []
	except Exception:
		all_graph_items = []

	cov = coverage(rec_items, all_graph_items)
	return {"coverage": cov, "num_recommended": len(rec_items), "num_items": len(all_graph_items)}


def save_metrics(metrics: dict):
	_, results = _paths()
	out = results / "metrics_report.txt"
	lines = [f"{k}: {v}" for k, v in sorted(metrics.items())]
	out.write_text("\n".join(lines), encoding="utf-8")
	return out


def main():
	metrics = evaluate_sample()
	out = save_metrics(metrics)
	print(f"Metrics written to {out}")
	for k, v in metrics.items():
		print(f" - {k}: {v}")


if __name__ == "__main__":
	main()

