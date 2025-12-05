"""Build a simple user-item bipartite graph from ratings.

This is a minimal, safe-to-run stub. It gracefully handles missing or
empty data files and still produces an (empty) graph artifact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple


def _project_paths() -> Tuple[Path, Path, Path]:
	# src/ -> project root
	root = Path(__file__).resolve().parent.parent
	data = root / "data"
	results = root / "results"
	results.mkdir(parents=True, exist_ok=True)
	return root, data, results


def _read_ratings_tsv(path: Path):
	"""Read ratings from a tab-separated file: user_id, item_id, rating, ts?"""
	import pandas as pd

	cols = ["user_id", "item_id", "rating", "timestamp"]
	if not path.exists() or path.stat().st_size == 0:
		return pd.DataFrame(columns=cols)
	try:
		df = pd.read_csv(path, sep="\t", names=cols, header=None, engine="python")
		# Coerce types
		for c in ("user_id", "item_id"):
			df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
		df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
		df = df.dropna(subset=["user_id", "item_id"]).copy()
		df["user_id"] = df["user_id"].astype(int)
		df["item_id"] = df["item_id"].astype(int)
		return df
	except Exception:
		# Fallback to empty
		return pd.DataFrame(columns=cols)


def build_user_item_graph(ratings_df):
	"""Return a NetworkX graph with user_*/item_* nodes and weighted edges."""
	import networkx as nx

	G = nx.Graph()
	if ratings_df is None or ratings_df.empty:
		return G

	# Add nodes and edges
	for row in ratings_df.itertuples(index=False):
		u = f"user_{int(row.user_id)}"
		i = f"item_{int(row.item_id)}"
		G.add_node(u, bipartite="user")
		G.add_node(i, bipartite="item")
		# Use latest rating if duplicate appears
		G.add_edge(u, i, weight=float(row.rating) if getattr(row, "rating", None) is not None else 1.0)
	return G


def save_graph(G, out_path: Path):
	import networkx as nx

	out_path.parent.mkdir(parents=True, exist_ok=True)
	nx.write_gpickle(G, out_path)


def main() -> Path:
	root, data, results = _project_paths()
	ratings_path = data / "u.data"
	out_path = results / "user_item_graph.gpickle"

	ratings_df = _read_ratings_tsv(ratings_path)
	G = build_user_item_graph(ratings_df)
	save_graph(G, out_path)

	# Print a tiny summary for CLI feedback
	try:
		import networkx as nx  # noqa: F401
		n_users = sum(1 for n, d in G.nodes(data=True) if d.get("bipartite") == "user")
		n_items = sum(1 for n, d in G.nodes(data=True) if d.get("bipartite") == "item")
		n_edges = G.number_of_edges()
		print(f"Graph saved to {out_path}")
		print(f"Users: {n_users}, Items: {n_items}, Interactions: {n_edges}")
	except Exception:
		pass

	return out_path


if __name__ == "__main__":
	main()

