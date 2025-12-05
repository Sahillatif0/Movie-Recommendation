from pathlib import Path
from flask import (
    Flask,
    render_template,
    request,
    send_file,
    Response,
    redirect,
    url_for,
    session,
)

from data_loader import load_data
from graph_model import GraphRecommender
from utils import ALGORITHM_NAMES

BASE_DIR = Path(__file__).resolve().parent
GRAPH_HTML = BASE_DIR / "templates" / "graph.html"
HEATMAP_PATH = BASE_DIR / "static" / "images" / "heatmap.png"

app = Flask(__name__)
app.secret_key = "dev-secret"

ratings_df, movies_df, merged_df = load_data()
recommender = GraphRecommender(ratings_df, movies_df, sample_size=20)


def _patch_graph_html(path: Path, lock_sample: bool):
    if not path.exists():
        return
    html = path.read_text(encoding="utf-8")
    lock_label = "Unlock sample" if lock_sample else "Lock sample"
    lock_toggle = "0" if lock_sample else "1"
    nav = (
        "<link rel=\"stylesheet\" href=\"/static/css/style.css\">"
        "<nav class=\"navbar\"><div class=\"logo\">Graph-Based Recs</div>"
        "<div class=\"nav-links\">"
        "<a href=\"/\">Home</a>"
        "<a class=\"active\" data-graph-link=\"1\" href=\"/graph\">Graph</a>"
        "<a href=\"/matrix\">Matrix</a>"
        "<a href=\"/recommend\">Recommend</a>"
        "</div>"
        "<div class=\"nav-actions\">"
        "<a class=\"btn tertiary\" data-graph-refresh=\"1\" data-refresh-value=\"1\" href=\"/graph?refresh=1\">Reshuffle graph</a>"
        f"<a class=\"btn secondary\" data-graph-lock=\"1\" data-lock-value=\"{lock_toggle}\" href=\"/graph?lock={lock_toggle}\">{lock_label}</a>"
        "</div></nav>"
        "<div class=\"page-wrapper\">"
        "<div class=\"graph-toolbar\">"
        "<div>"
        "<p class=\"eyebrow\">Graph View</p>"
        "<h2>Sampled user-movie graph</h2>"
        "<p class=\"muted\">Refresh to see a new random sample of users and movies.</p>"
        "</div>"
        "<div class=\"cta-group\">"
        "<a class=\"btn secondary\" data-graph-refresh=\"1\" data-refresh-value=\"1\" href=\"/graph?refresh=1\">Refresh sample</a>"
        "<a class=\"btn tertiary\" data-graph-refresh=\"1\" data-refresh-value=\"0\" href=\"/graph?refresh=0\">Keep current sample</a>"
        "<a class=\"btn secondary\" data-graph-matrix=\"1\" href=\"/graph/adjacency\">Graph adjacency matrix</a>"
        "</div>"
        "</div>"
        "<script>"
        "(function(){"
        "const params=new URLSearchParams(window.location.search);"
        "document.querySelectorAll('[data-graph-refresh]').forEach(link=>{"
        "const p=new URLSearchParams(params);"
        "p.set('refresh', link.dataset.refreshValue || '1');"
        "link.href='/graph?'+p.toString();"
        "});"
        "document.querySelectorAll('[data-graph-lock]').forEach(link=>{"
        "const p=new URLSearchParams(params);"
        "p.set('lock', link.dataset.lockValue || '1');"
        "link.href='/graph?'+p.toString();"
        "});"
        "document.querySelectorAll('[data-graph-matrix]').forEach(link=>{"
        "const p=new URLSearchParams(params);"
        "link.href='/graph/adjacency?'+p.toString();"
        "});"
        "document.querySelectorAll('[data-graph-link]').forEach(link=>{"
        "const p=new URLSearchParams(params);"
        "link.href='/graph?'+p.toString();"
        "});"
        "})();"
        "</script>"
    )
    html = html.replace("<body>", f"<body>{nav}")
    html = html.replace("</body>", "</div></body>")
    path.write_text(html, encoding="utf-8")


@app.route("/")
def index():
    return render_template(
        "index.html",
        users=recommender.selected_users,
        algorithms=ALGORITHM_NAMES,
    )


@app.route("/graph")
def graph():
    mode = request.args.get("mode", "all")
    selected_user = request.args.get("user_id", type=int)
    algorithm = request.args.get("algorithm", "cosine")
    top_n_default = 20 if mode == "recommendations" else 8
    top_n = request.args.get("top", type=int) or top_n_default
    lock_param = request.args.get("lock")
    if lock_param is not None:
        session["lock_sample"] = lock_param == "1"
    lock_sample = session.get("lock_sample", False)

    refresh_param = request.args.get("refresh")
    if refresh_param is None:
        refresh = not lock_sample
    else:
        refresh = refresh_param == "1"

    if mode == "all":
        if refresh:
            recommender.refresh()
        recommender.export_pyvis(GRAPH_HTML)
    elif mode == "recommendations" and selected_user:
        # Do not auto-refresh here to keep the selected user in scope.
        recommender.export_recommendation_graph(
            selected_user, algorithm=algorithm, output_path=GRAPH_HTML, top_n=top_n
        )
    else:
        recommender.export_pyvis(GRAPH_HTML)
    _patch_graph_html(GRAPH_HTML, lock_sample=lock_sample)
    return render_template("graph.html")


@app.route("/matrix")
def matrix():
    table = recommender.adjacency_table()
    if request.args.get("download") == "1":
        csv_data = table.to_csv()
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=adjacency.csv"},
        )

    recommender.generate_heatmap(HEATMAP_PATH)
    headers = [str(col) for col in table.columns]
    rows = [(str(idx), [int(val) for val in table.loc[idx]]) for idx in table.index]
    return render_template(
        "matrix.html",
        headers=headers,
        rows=rows,
        heatmap_url="/static/images/heatmap.png",
    )


@app.route("/recommend", methods=["GET", "POST"])
def recommend():
    results = []
    selected_user = None
    selected_algo = None

    if request.method == "POST":
        selected_user = int(request.form.get("user_id"))
        selected_algo = request.form.get("algorithm", "cosine")
        recommendations = recommender.recommend(selected_user, selected_algo, top_n=20)
        results = [
            {"title": title, "score": round(score, 4)} for title, score in recommendations
        ]

    return render_template(
        "recommend.html",
        users=recommender.selected_users,
        algorithms=ALGORITHM_NAMES,
        results=results,
        selected_user=selected_user,
        selected_algo=selected_algo,
        top_n=len(results) or 20,
    )


@app.route("/recommend/matrix")
def recommend_matrix():
    user_id = request.args.get("user_id", type=int)
    algorithm = request.args.get("algorithm", "cosine")
    top_n = request.args.get("top", type=int) or 20
    download = request.args.get("download") == "1"
    if not user_id:
        return redirect(url_for("recommend"))

    recs = recommender.recommend_with_ids(user_id, algorithm=algorithm, top_n=top_n)
    headers = [title for _, title, _ in recs]
    scores = [round(score, 4) for *_, score in recs]

    if download:
        csv_rows = [["user_id"] + [str(h) for h in headers]]
        csv_rows.append([user_id] + scores)
        csv_str = "\n".join(",".join(map(str, row)) for row in csv_rows)
        return Response(
            csv_str,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=recommendation_matrix_user_{user_id}.csv"},
        )

    return render_template(
        "recommend_matrix.html",
        user_id=user_id,
        algorithm=ALGORITHM_NAMES.get(algorithm, algorithm),
        headers=headers,
        scores=scores,
        top_n=top_n,
    )


@app.route("/graph/adjacency")
def graph_adjacency():
    mode = request.args.get("mode", "all")
    user_id = request.args.get("user_id", type=int)
    algorithm_key = request.args.get("algorithm", "cosine")
    top_n_default = 20 if mode == "recommendations" else 8
    top_n = request.args.get("top", type=int) or top_n_default

    if mode == "recommendations" and user_id:
        recs = recommender.recommend_with_ids(user_id, algorithm=algorithm_key, top_n=top_n)
        headers = [title for _, title, _ in recs]
        rows = [("User " + str(user_id), [1 for _ in recs])]
        subtitle = f"User {user_id} — Top {top_n} (Algorithm: {ALGORITHM_NAMES.get(algorithm_key, algorithm_key)})"
    else:
        table = recommender.adjacency_table()
        headers = [str(col) for col in table.columns]
        rows = [(str(idx), [1 if int(val) > 0 else 0 for val in table.loc[idx]]) for idx in table.index]
        subtitle = "Current sampled graph adjacency (users x movies, 1 = edge)"

    return render_template(
        "graph_matrix.html",
        mode=mode,
        headers=headers,
        rows=rows,
        subtitle=subtitle,
    )


if __name__ == "__main__":
    app.run(debug=True)
