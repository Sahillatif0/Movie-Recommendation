# Movie Recommendation (Graph-based Starter)

This repository scaffolds a simple, graph-based movie recommendation workflow. It creates a user–item bipartite graph from ratings and provides a tiny heuristic recommender plus a stub evaluation.

The code is intentionally lightweight and safe to run even without real data; it gracefully handles missing/empty files and still produces artifacts.

## Repository layout

- `data/` — place dataset files here (e.g., `u.data`, `u.item` from MovieLens 100k)
- `notebooks/` — scratch notebooks for exploration
- `src/` — Python source code
	- `build_graph.py` — builds a bipartite NetworkX graph from ratings
	- `recommend.py` — simple 2-hop co-occurrence recommendations
	- `evaluate.py` — tiny placeholder metrics and report writer
	- `utils.py` — small helpers
- `results/` — generated artifacts (graph, CSVs, metrics)
- `presentation/`, `report/` — deliverables

## Quickstart

1) Create a Python environment and install dependencies

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Put data files into `data/`

- Expected ratings file: `data/u.data` with tab-separated values: `user_id\titem_id\trating\ttimestamp`
- Item metadata (optional): `data/u.item` (MovieLens format, pipe-separated). Not required for the graph build stub.

3) Build the graph and generate recommendations

```powershell
python -m src.build_graph
python -m src.recommend --user 1 --topk 10
python -m src.evaluate
```

Artifacts will be written to `results/`:

- `user_item_graph.gpickle` — networkx graph
- `recommendation_samples.csv` — top-K items for the provided user
- `metrics_report.txt` — basic metrics (coverage placeholder)

## Notes

- The recommender uses a simple and transparent heuristic (2-hop co-occurrence). It’s a good baseline and easy to extend.
- You can replace it with more advanced approaches (item-item similarities, matrix factorization, GNNs) as you iterate.
- If the dataset isn’t present, the scripts still run and produce empty artifacts to keep the pipeline consistent.

