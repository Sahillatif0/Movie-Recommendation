import pandas as pd
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "ml-100k"


def load_data(data_path: Path = DATA_PATH):
    """Load ratings and movie metadata, return merged DataFrames."""
    data_file = data_path / "u.data"
    item_file = data_path / "u.item"

    ratings_cols = ["user_id", "movie_id", "rating", "timestamp"]
    ratings = pd.read_csv(data_file, sep="\t", names=ratings_cols, encoding="latin-1")

    item_cols = [
        "movie_id",
        "title",
        "release_date",
        "video_release_date",
        "imdb_url",
    ] + [f"genre_{i}" for i in range(19)]
    movies = pd.read_csv(item_file, sep="|", names=item_cols, encoding="latin-1")

    merged = ratings.merge(movies[["movie_id", "title"]], on="movie_id", how="left")
    return ratings, movies, merged


def get_user_movie_matrix(ratings_subset):
    """Pivot a ratings subset into a user-movie matrix with zeros for missing ratings."""
    matrix = ratings_subset.pivot_table(
        index="user_id", columns="movie_id", values="rating", fill_value=0
    )
    return matrix
