import math
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
                size=58 if attrs.get("bipartite") == "user" else 12,
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
        algorithm = (algorithm or "cosine").lower()
        if algorithm in {"jaccard", "adamic", "resource"}:
            return self._recommend_similarity_sets(user_id, algorithm, top_n)
        if algorithm == "preferential":
            return self._recommend_preferential_attachment(user_id, top_n)
        if algorithm == "pagerank":
            return self._recommend_personalized_pagerank(user_id, top_n)
        return self._recommend_collaborative(user_id, top_n)

    def _recommend_collaborative(
        self, user_id: int, top_n: int
    ) -> List[Tuple[int, str, float]]:
        if user_id not in self.matrix.index:
            return []

        centered_matrix = self._mean_centered_matrix()
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

    def _recommend_similarity_sets(
        self, user_id: int, algorithm: str, top_n: int
    ) -> List[Tuple[int, str, float]]:
        if user_id not in self.matrix.index:
            return []

        user_ratings = self.matrix.loc[user_id]
        rated = user_ratings[user_ratings > 0]
        if rated.empty:
            return []

        candidates = user_ratings[user_ratings == 0].index
        if candidates.empty:
            return []

        binary_matrix = (self.matrix > 0).astype(bool)
        user_degrees = binary_matrix.sum(axis=1).to_dict()
        watchers_cache = {}

        def watchers(movie_id):
            movie_id = int(movie_id)
            if movie_id not in watchers_cache:
                col = binary_matrix[movie_id]
                watchers_cache[movie_id] = set(col[col].index)
            return watchers_cache[movie_id]

        scored = []
        for movie_id in candidates:
            candidate_watchers = watchers(movie_id)
            score = 0.0
            for seen_id, seen_rating in rated.items():
                seen_watchers = watchers(seen_id)
                intersection = candidate_watchers & seen_watchers
                if not intersection:
                    continue
                if algorithm == "jaccard":
                    union = candidate_watchers | seen_watchers
                    sim = len(intersection) / len(union) if union else 0.0
                elif algorithm == "adamic":
                    sim = 0.0
                    for user in intersection:
                        deg = user_degrees.get(user, 0)
                        if deg <= 1:
                            continue
                        sim += 1.0 / math.log(deg)
                else:  # resource
                    sim = 0.0
                    for user in intersection:
                        deg = user_degrees.get(user, 0)
                        if deg == 0:
                            continue
                        sim += 1.0 / deg
                if sim <= 0:
                    continue
                score += sim * float(seen_rating)
            if score <= 0:
                continue
            scored.append((int(movie_id), self._movie_title(int(movie_id)), float(score)))

        scored.sort(key=lambda x: x[2], reverse=True)
        if not scored:
            return []

        max_score = max(item[2] for item in scored)
        if max_score <= 0:
            return scored[:top_n]

        scale = 5.0 / max_score
        normalized = []
        for movie_id, title, score in scored[:top_n]:
            capped = min(max(score * scale, 0.0), 5.0)
            normalized.append((movie_id, title, float(capped)))
        return normalized

    def _recommend_preferential_attachment(
        self, user_id: int, top_n: int
    ) -> List[Tuple[int, str, float]]:
        if user_id not in self.matrix.index:
            return []

        user_ratings = self.matrix.loc[user_id]
        rated = user_ratings[user_ratings > 0]
        if rated.empty:
            return []

        candidates = user_ratings[user_ratings == 0].index
        if not len(candidates):
            return []

        binary_matrix = (self.matrix > 0).astype(int)
        user_degree = int(binary_matrix.loc[user_id].sum())
        watchers_cache = {}

        def watchers(movie_id):
            movie_id = int(movie_id)
            if movie_id not in watchers_cache:
                col = binary_matrix[movie_id]
                watchers_cache[movie_id] = set(col[col > 0].index)
            return watchers_cache[movie_id]

        scored = []
        for movie_id in candidates:
            candidate_watchers = watchers(movie_id)
            movie_degree = len(candidate_watchers)
            if movie_degree == 0:
                continue

            overlap_mass = 0
            for seen_id in rated.index:
                overlap_mass += len(candidate_watchers & watchers(seen_id))

            if overlap_mass == 0:
                continue

            score = float(user_degree + 1) * float(movie_degree + 1) * math.log(1 + overlap_mass)
            scored.append((int(movie_id), self._movie_title(int(movie_id)), score))

        scored.sort(key=lambda x: x[2], reverse=True)
        if not scored:
            return []

        max_score = max(item[2] for item in scored)
        scale = 5.0 / max_score if max_score else 1.0
        normalized = []
        for movie_id, title, score in scored[:top_n]:
            normalized.append((movie_id, title, float(min(score * scale, 5.0))))
        return normalized

    def _recommend_personalized_pagerank(
        self, user_id: int, top_n: int
    ) -> List[Tuple[int, str, float]]:
        user_node = _user_node(user_id)
        if user_node not in self.graph or user_id not in self.matrix.index:
            return []

        personalization = {node: 0.0 for node in self.graph.nodes}
        personalization[user_node] = 1.0

        try:
            scores = nx.pagerank(self.graph, alpha=0.85, personalization=personalization, max_iter=200)
        except nx.NetworkXError:
            return []

        user_ratings = self.matrix.loc[user_id]
        candidates = [movie_id for movie_id in user_ratings.index if user_ratings[movie_id] == 0]
        scored = []
        for movie_id in candidates:
            node_id = _movie_node(int(movie_id))
            score = scores.get(node_id, 0.0)
            if score <= 0:
                continue
            scored.append((int(movie_id), self._movie_title(int(movie_id)), float(score)))

        scored.sort(key=lambda x: x[2], reverse=True)
        if not scored:
            return []

        max_score = max(item[2] for item in scored)
        scale = 5.0 / max_score if max_score else 1.0
        normalized = []
        for movie_id, title, score in scored[:top_n]:
            normalized.append((movie_id, title, float(min(score * scale, 5.0))))
        return normalized

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
            size=52,
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
                    size=34,
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

    def node_profile(self, node_id: str) -> dict:
        if not node_id or self.matrix is None:
            return {}
        node_id = node_id.strip()
        if node_id.startswith(USER_PREFIX):
            try:
                return self._user_node_profile(int(node_id.lstrip(USER_PREFIX)))
            except ValueError:
                return {}
        if node_id.startswith(MOVIE_PREFIX):
            try:
                return self._movie_node_profile(int(node_id.lstrip(MOVIE_PREFIX)))
            except ValueError:
                return {}
        return {}

    def _user_node_profile(self, user_id: int) -> dict:
        if user_id not in self.matrix.index:
            return {}

        row = self.matrix.loc[user_id]
        favorites = row[row > 0].sort_values(ascending=False)
        top_movies = [
            {
                "movie_id": int(mid),
                "title": self._movie_title(int(mid)),
                "rating": float(score),
            }
            for mid, score in favorites.head(5).items()
        ]
        avg_rating = float(favorites.mean()) if not favorites.empty else 0.0

        binary_matrix = (self.matrix > 0).astype(bool)
        user_watchlist = set(binary_matrix.loc[user_id][binary_matrix.loc[user_id]].index)

        similar_users = []
        for other_id in self.matrix.index:
            if other_id == user_id:
                continue
            other_watchlist = set(binary_matrix.loc[other_id][binary_matrix.loc[other_id]].index)
            shared = user_watchlist & other_watchlist
            if not shared:
                continue
            shared_titles = [self._movie_title(int(mid)) for mid in sorted(shared)[:3]]
            similar_users.append(
                {
                    "user_id": int(other_id),
                    "overlap": len(shared),
                    "shared_titles": shared_titles,
                }
            )

        similar_users.sort(key=lambda item: item["overlap"], reverse=True)
        similar_users = similar_users[:4]

        return {
            "type": "user",
            "id": int(user_id),
            "degree": len(user_watchlist),
            "avg_rating": avg_rating,
            "top_movies": top_movies,
            "similar_users": similar_users,
        }

    def _movie_node_profile(self, movie_id: int) -> dict:
        if movie_id not in self.matrix.columns:
            return {}

        column = self.matrix[movie_id]
        watchers = column[column > 0].sort_values(ascending=False)
        watchers_payload = [
            {"user_id": int(uid), "rating": float(rating)} for uid, rating in watchers.head(6).items()
        ]
        avg_rating = float(watchers.mean()) if not watchers.empty else 0.0

        binary_matrix = (self.matrix > 0).astype(bool)
        movie_watchers = set(binary_matrix[movie_id][binary_matrix[movie_id]].index)

        related = []
        for other_movie in self.matrix.columns:
            if other_movie == movie_id:
                continue
            other_watchers = set(binary_matrix[other_movie][binary_matrix[other_movie]].index)
            overlap = len(movie_watchers & other_watchers)
            if overlap == 0:
                continue
            related.append(
                {
                    "movie_id": int(other_movie),
                    "title": self._movie_title(int(other_movie)),
                    "overlap": overlap,
                }
            )

        related.sort(key=lambda item: item["overlap"], reverse=True)
        related = related[:5]

        return {
            "type": "movie",
            "id": int(movie_id),
            "title": self._movie_title(int(movie_id)),
            "degree": len(movie_watchers),
            "avg_rating": avg_rating,
            "watchers": watchers_payload,
            "related_movies": related,
        }
