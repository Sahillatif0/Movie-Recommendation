from datetime import datetime


ALGORITHM_NAMES = {
    "cosine": "Cosine (item-item)",
    "jaccard": "Jaccard Coefficient",
    "adamic": "Adamic/Adar Index",
    "resource": "Resource Allocation Index",
}


def format_timestamp(ts: int) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:
        return ""
