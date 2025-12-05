import random
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from pyvis.network import Network

from data_loader import get_user_movie_matrix


USER_PREFIX = "U"
MOVIE_PREFIX = "M"


def _user_node(user_id: int) -> str:
    return f"{USER_PREFIX}{user_id}"


def _movie_node(movie_id: int) -> str:
    return f"{MOVIE_PREFIX}{movie_id}"


def _unwrap_movie(node: str) -> int:
    return int(node.lstrip(MOVIE_PREFIX))


class GraphRecommender:
    """Builds a bipartite user-movie graph and runs link prediction for recommendations."""

    def __init__(self, ratings_df, movies_df, sample_size: int = 10):
        self.ratings_df = ratings_df
        self.movies_df = movies_df
        self.sample_size = sample_size
        self.graph = nx.Graph()
        self.selected_users: List[int] = []
        self.selected_movies: List[int] = []
        self.matrix = None
        self.refresh()

    def refresh(self):
        """Resample users and rebuild graph/matrix."""
        self.selected_users = self._pick_users()
        subset = self.ratings_df[self.ratings_df["user_id"].isin(self.selected_users)]
        self.matrix = get_user_movie_matrix(subset)
        self.selected_movies = list(self.matrix.columns)
        self.graph = self._build_graph(subset)

    def _pick_users(self) -> List[int]:
        unique_users = self.ratings_df["user_id"].unique().tolist()
        if len(unique_users) <= self.sample_size:
            return unique_users
        return random.sample(unique_users, self.sample_size)

    def _build_graph(self, ratings_subset) -> nx.Graph:
        G = nx.Graph()
        # Add user nodes
        for uid in self.selected_users:
            G.add_node(_user_node(uid), label=str(uid), bipartite="user", color="#3F8EFC")

        # Add movie nodes
        movies_in_subset = ratings_subset["movie_id"].unique().tolist()
        for mid in movies_in_subset:
            title = self._movie_title(mid)
            G.add_node(
                _movie_node(mid),
                label=title,
                title=title,
                bipartite="movie",
                color="#F5A623",
            )

        # Add edges with rating weight
        for _, row in ratings_subset.iterrows():
            G.add_edge(
                _user_node(int(row.user_id)),
                _movie_node(int(row.movie_id)),
                weight=float(row.rating),
                title=f"Rating: {row.rating}",
            )
        return G

    def export_pyvis(self, output_path: Path):
        net = Network(height="650px", width="100%", bgcolor="#0d1117", font_color="#e0e6ed")
        net.barnes_hut()

        for node, attrs in self.graph.nodes(data=True):
            net.add_node(
                node,
                label=attrs.get("label", node),
                color=attrs.get("color"),
                title=attrs.get("title", attrs.get("label", node)),
                shape="dot",
                size=18 if attrs.get("bipartite") == "user" else 12,
                group=attrs.get("bipartite"),
            )

        for u, v, attrs in self.graph.edges(data=True):
            net.add_edge(u, v, value=attrs.get("weight", 1), title=attrs.get("title", ""))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        net.write_html(str(output_path), notebook=False, open_browser=False)

    def adjacency_table(self):
        table = self.matrix.copy()
        table.index = [int(idx) for idx in table.index]
        table.columns = [int(col) for col in table.columns]
        return table.sort_index(axis=0).sort_index(axis=1)

    def generate_heatmap(self, output_path: Path):
        data = self.matrix.values
        plt.figure(figsize=(10, 6))
        plt.imshow(data, cmap="magma", aspect="auto")
        plt.colorbar(label="Rating")
        plt.xticks(
            ticks=np.arange(len(self.matrix.columns)),
            labels=[str(int(c)) for c in self.matrix.columns],
            rotation=90,
            fontsize=6,
        )
        plt.yticks(
            ticks=np.arange(len(self.matrix.index)),
            labels=[str(int(r)) for r in self.matrix.index],
            fontsize=7,
        )
        plt.title("User-Movie Ratings Heatmap", fontsize=12)
        plt.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=200)
        plt.close()

    def recommend(self, user_id: int, algorithm: str = "cosine", top_n: int = 5) -> List[Tuple[int, float]]:
        results = self.recommend_with_ids(user_id, algorithm=algorithm, top_n=top_n)
        return [(title, score) for _, title, score in results]

    def recommend_with_ids(
        self, user_id: int, algorithm: str = "cosine", top_n: int = 5
    ) -> List[Tuple[int, str, float]]:
        if user_id not in self.matrix.index:
            return []

        centered_matrix = self._mean_centered_matrix()
        # Item-based collaborative filtering using cosine similarity between movie rating vectors.
        user_ratings = self.matrix.loc[user_id]
        rated = user_ratings[user_ratings > 0]
        if rated.empty:
            return []

        candidates = user_ratings[user_ratings == 0]
        movie_vectors = centered_matrix  # rows: users, cols: movies

        scored = []
        for movie_id in candidates.index:
            cand_vec = movie_vectors[movie_id].values
            weighted_score = 0.0
            sim_sum = 0.0
            for seen_id, seen_rating in rated.items():
                seen_vec = movie_vectors[seen_id].values
                sim = self._cosine_similarity(cand_vec, seen_vec)
                if sim <= 0:
                    continue
                weighted_score += sim * seen_rating
                sim_sum += sim
            score = weighted_score / sim_sum if sim_sum > 0 else 0.0
            scored.append((movie_id, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_n]
        results = []
        for movie_id, score in top:
            results.append((int(movie_id), self._movie_title(int(movie_id)), float(score)))
        return results

    @staticmethod
    def _cosine_similarity(vec_a, vec_b) -> float:
        denom = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
        if denom == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / denom)

    def _mean_centered_matrix(self):
        """Return a user-mean-centered rating matrix for similarity calculations."""
        df = self.matrix.astype(float).copy()
        # Replace zeros (missing ratings) with NaN to compute per-user means correctly.
        df_nan = df.replace(0, np.nan)
        user_means = df_nan.mean(axis=1).fillna(0)

        # Subtract user mean from rated entries; keep missing as zero.
        df_centered = df_nan.sub(user_means, axis=0).fillna(0)
        return df_centered

    def export_recommendation_graph(
        self, user_id: int, algorithm: str, output_path: Path, top_n: int = 5
    ):
        """Create a PyVis graph that only shows the selected user's recommendations."""
        recommendations = self.recommend_with_ids(user_id, algorithm=algorithm, top_n=top_n)

        net = Network(height="650px", width="100%", bgcolor="#0d1117", font_color="#e0e6ed")
        net.barnes_hut()

        user_node = _user_node(user_id)
        net.add_node(
            user_node,
            label=f"User {user_id}",
            color="#3F8EFC",
            title=f"Recommendations for User {user_id}",
            shape="dot",
            size=22,
            group="user",
        )

        if not recommendations:
            net.add_node(
                "no_recs",
                label="No recommendations",
                color="#94a3b8",
                title="No recommendations available for this user.",
                shape="box",
            )
        else:
            for movie_id, title, score in recommendations:
                movie_node = _movie_node(movie_id)
                net.add_node(
                    movie_node,
                    label=title,
                    title=f"{title} (score: {score:.4f})",
                    color="#34d399",
                    shape="dot",
                    size=14,
                    group="recommendation",
                )
                net.add_edge(
                    user_node,
                    movie_node,
                    value=score if score > 0 else 0.1,
                    title=f"Predicted score: {score:.4f}",
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        net.write_html(str(output_path), notebook=False, open_browser=False)

    def _movie_title(self, movie_id: int) -> str:
        match = self.movies_df[self.movies_df["movie_id"] == movie_id]
        if not match.empty:
            return match.iloc[0].title
        return f"Movie {movie_id}"
