import re
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
    jsonify,
)

from data_loader import load_data
from graph_model import GraphRecommender
from utils import ALGORITHM_NAMES

BASE_DIR = Path(__file__).resolve().parent
GRAPH_HTML = BASE_DIR / "templates" / "graph.html"
HEATMAP_PATH = BASE_DIR / "static" / "images" / "heatmap.png"

NETWORK_DIV_ESCAPED = '<div id=\"mynetwork\" class=\"card-body\"></div>'
NETWORK_DIV_PLAIN = '<div id="mynetwork" class="card-body"></div>'
LOADER_MARKUP_ESCAPED = f"""{NETWORK_DIV_ESCAPED}
                        <div id=\"loadingBar\">
                            <div class=\"loader-aurora\"></div>
                            <div class=\"graph-loader-panel\">
                                <p class=\"loader-kicker\">Building graph sample</p>
                                <h3 id=\"loader-stage\">Initializing layout</h3>
                                <p class=\"loader-hint\">We stabilize the network so clusters stay readable once it renders.</p>
                                <div class=\"loader-progress\">
                                    <div id=\"bar\"></div>
                                </div>
                                <div class=\"loader-meta\">
                                    <span id=\"text\">0%</span>
                                    <span id=\"loader-tip\">Hang tight, this only takes a moment.</span>
                                </div>
                            </div>
                        </div>"""
LOADER_MARKUP_PLAIN = LOADER_MARKUP_ESCAPED.replace('\\"', '"')

app = Flask(__name__)
app.secret_key = "dev-secret"

ratings_df, movies_df, merged_df = load_data()
recommender = GraphRecommender(ratings_df, movies_df, sample_size=20)


def _patch_graph_html(path: Path, lock_sample: bool, show_loader: bool = True):
    if not path.exists():
        return
    html = path.read_text(encoding="utf-8")
    lock_label = "Unlock sample" if lock_sample else "Lock sample"
    lock_toggle = "0" if lock_sample else "1"
    
    # Add script to load our custom JS
    script_loader = '<script src="/static/js/script.js" defer></script>'
    
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
    html = html.replace("</body>", f"{script_loader}</div></body>")
    html = _modernize_loader_html(html, show_loader=show_loader)
    path.write_text(html, encoding="utf-8")


def _strip_loader_overlay(html: str) -> str:
    for markup, replacement in (
        (LOADER_MARKUP_ESCAPED, NETWORK_DIV_ESCAPED),
        (LOADER_MARKUP_PLAIN, NETWORK_DIV_PLAIN),
    ):
        if markup in html:
            return html.replace(markup, replacement, 1)
    return html


def _modernize_loader_html(html: str, show_loader: bool = True) -> str:
    if not show_loader:
        return _strip_loader_overlay(html)

    if "graph-loader-panel" in html:
        return html

    legacy_css_patterns = [
        r"\s*#loadingBar\s*\{[^}]*\}",
        r"\s*#bar\s*\{[^}]*\}",
        r"\s*#border\s*\{[^}]*\}",
        r"\s*#text\s*\{[^}]*\}",
        r"\s*div\.outerBorder\s*\{[^}]*\}",
    ]
    for pattern in legacy_css_patterns:
        html = re.sub(pattern, "", html, count=1, flags=re.MULTILINE | re.DOTALL)

    custom_css = """
             .graph-card {
                 position: relative;
                 overflow: hidden;
             }

             #loadingBar {
                 position: absolute;
                 inset: 0;
                 display: flex;
                 align-items: center;
                 justify-content: center;
                 padding: 1.5rem;
                 background: radial-gradient(circle at 20% 20%, rgba(99,102,241,0.15), transparent),
                              radial-gradient(circle at 80% 0%, rgba(45,212,191,0.12), transparent),
                              rgba(13,17,23,0.88);
                 backdrop-filter: blur(8px);
                 transition: opacity 0.4s ease;
                 z-index: 12;
             }

             .graph-loader-panel {
                 position: relative;
                 width: min(420px, 90vw);
                 border-radius: 22px;
                 padding: 1.75rem;
                 background: rgba(15,15,25,0.92);
                 border: 1px solid rgba(148,163,184,0.25);
                 box-shadow: 0 25px 80px rgba(15,23,42,0.65);
                 color: #e2e8f0;
                 z-index: 2;
             }

             .loader-kicker {
                 font-size: 0.75rem;
                 letter-spacing: 0.08em;
                 text-transform: uppercase;
                 color: #a5b4fc;
                 margin: 0 0 0.35rem;
             }

             #loader-stage {
                 font-size: 1.35rem;
                 margin: 0 0 0.5rem;
                 color: #f8fafc;
             }

             .loader-hint {
                 margin: 0;
                 color: #94a3b8;
                 font-size: 0.9rem;
             }

             .loader-progress {
                 width: 100%;
                 height: 10px;
                 border-radius: 999px;
                 background: rgba(15,118,110,0.2);
                 overflow: hidden;
                 margin-top: 1.5rem;
             }

             #bar {
                 width: 8%;
                 height: 100%;
                 border-radius: inherit;
                 background: linear-gradient(90deg, #22d3ee, #818cf8);
                 box-shadow: 0 0 25px rgba(129,140,248,0.6);
                 transition: width 0.3s ease;
             }

             .loader-meta {
                 display: flex;
                 justify-content: space-between;
                 align-items: center;
                 margin-top: 0.85rem;
                 font-size: 0.85rem;
                 color: #94a3b8;
             }

             #text {
                 font-weight: 700;
                 font-size: 1rem;
                 color: #f1f5f9;
             }

             #loader-tip {
                 font-size: 0.85rem;
                 color: #cbd5f5;
             }

             .loader-aurora {
                 position: absolute;
                 inset: -40% auto auto -20%;
                 width: 220px;
                 height: 220px;
                 background: radial-gradient(circle, rgba(14,165,233,0.4), transparent 60%);
                 filter: blur(8px);
                 animation: pulse 4s ease-in-out infinite;
                 z-index: 1;
             }

             @keyframes pulse {
                 0% { opacity: 0.65; transform: scale(0.9); }
                 50% { opacity: 1; transform: scale(1.05); }
                 100% { opacity: 0.65; transform: scale(0.9); }
             }
    """

    if "graph-card {" not in html:
        html = html.replace("        </style>", f"{custom_css}\n        </style>", 1)

    html = re.sub(r"\s*<div id=\"loadingBar\">[\s\S]*?</div>\s*", "\n", html, count=1)
    html = re.sub(r"\s*<div class=\"outerBorder\">[\s\S]*?</div>\s*", "\n", html)
    html = re.sub(r"\s*<div id=\"border\">[\s\S]*?</div>\s*", "\n", html)

    html = html.replace('<div class="card" style="width: 100%">', '<div class="card graph-card" style="width: 100%">', 1)

    for target, replacement in (
        (NETWORK_DIV_ESCAPED, LOADER_MARKUP_ESCAPED),
        (NETWORK_DIV_PLAIN, LOADER_MARKUP_PLAIN),
    ):
        if target in html:
            html = html.replace(target, replacement, 1)
            break

    script_pattern = re.compile(
        r"\n\s+network\.on\(\"stabilizationProgress\"[\s\S]*?network\.once\(\"stabilizationIterationsDone\"[\s\S]*?\}\);\s*",
        re.MULTILINE,
    )

    new_script = """
                  
                      var loader = document.getElementById('loadingBar');
                      var loaderBar = document.getElementById('bar');
                      var loaderText = document.getElementById('text');
                      var loaderStage = document.getElementById('loader-stage');
                      var loaderTip = document.getElementById('loader-tip');
                      var loaderStages = [
                          { threshold: 0.2, stage: 'Collecting user nodes', tip: 'Sampling active viewers for this snapshot.' },
                          { threshold: 0.45, stage: 'Linking shared favorites', tip: 'Connecting users who loved the same titles.' },
                          { threshold: 0.75, stage: 'Untangling clusters', tip: 'Running physics to keep neighborhoods readable.' },
                          { threshold: 1, stage: 'Adding neon glow', tip: 'Finalizing styles before rendering the network.' }
                      ];

                      function updateLoaderStage(progress) {
                          if (!loaderStage || !loaderTip) {
                              return;
                          }
                          for (var i = 0; i < loaderStages.length; i++) {
                              if (progress <= loaderStages[i].threshold) {
                                  loaderStage.textContent = loaderStages[i].stage;
                                  loaderTip.textContent = loaderStages[i].tip;
                                  return;
                              }
                          }
                          var lastStage = loaderStages[loaderStages.length - 1];
                          loaderStage.textContent = lastStage.stage;
                          loaderTip.textContent = lastStage.tip;
                      }

                      function hideLoaderCompletely() {
                          if (!loader) {
                              return;
                          }
                          loader.style.opacity = 0;
                          setTimeout(function () {
                              loader.style.display = 'none';
                          }, 500);
                      }

                      network.on("stabilizationProgress", function(params) {
                          if (loader) {
                              loader.removeAttribute("style");
                          }
                          var widthFactor = params.iterations/params.total;
                          var clamped = Math.max(0.06, Math.min(1, widthFactor));
                          if (loaderBar) {
                              loaderBar.style.width = (clamped * 100) + '%';
                          }
                          if (loaderText) {
                              loaderText.innerHTML = Math.round(widthFactor*100) + '%';
                          }
                          updateLoaderStage(widthFactor);
                      });
                      network.once("stabilizationIterationsDone", function() {
                          if (loaderText) {
                              loaderText.innerHTML = '100%';
                          }
                          if (loaderBar) {
                              loaderBar.style.width = '100%';
                          }
                          updateLoaderStage(1);
                          hideLoaderCompletely();
                      });

                      setTimeout(function () {
                          if (!loader || loader.style.display === 'none') {
                              return;
                          }
                          if (loaderText) {
                              loaderText.innerHTML = '100%';
                          }
                          if (loaderBar) {
                              loaderBar.style.width = '100%';
                          }
                          updateLoaderStage(1);
                          hideLoaderCompletely();
                      }, 6000);
                  
    """

    html = script_pattern.sub(new_script, html, count=1)
    return html


def _normalize_for_blend(entries):
    normalized = {}
    for item in entries:
        movie_id = item["movie_id"]
        normalized[movie_id] = {
            "title": item["title"],
            "score": min(max(item["score"] / 5.0, 0.0), 1.0),
        }
    return normalized


def _blend_algorithm_scores(selected_algorithms, algo_results, blend_weight, top_n):
    if len(selected_algorithms) < 2:
        return []

    normalized_weight = max(0, min(int(blend_weight or 0), 100)) / 100.0
    primary_share = 1.0 - normalized_weight
    secondary_algorithms = selected_algorithms[1:]
    if not secondary_algorithms:
        return []

    secondary_share = normalized_weight
    secondary_per_algo = secondary_share / len(secondary_algorithms) if secondary_algorithms else 0.0

    combined = {}

    def accumulate(algo_key, weight):
        normalized = _normalize_for_blend(algo_results.get(algo_key, []))
        for movie_id, payload in normalized.items():
            bucket = combined.setdefault(
                movie_id,
                {"movie_id": movie_id, "title": payload["title"], "score": 0.0},
            )
            bucket["score"] += payload["score"] * weight

    accumulate(selected_algorithms[0], primary_share)
    for algo in secondary_algorithms:
        accumulate(algo, secondary_per_algo)

    ranked = sorted(combined.values(), key=lambda x: x["score"], reverse=True)
    blended = []
    for entry in ranked[:top_n]:
        blended.append(
            {
                "movie_id": entry["movie_id"],
                "title": entry["title"],
                "score": round(entry["score"] * 5.0, 3),
            }
        )
    return blended


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
    show_loader = mode != "recommendations"
    _patch_graph_html(GRAPH_HTML, lock_sample=lock_sample, show_loader=show_loader)
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
    algo_results = {}
    blended_results = []
    selected_user = None
    selected_algorithms = []
    blend_weight = 35
    blend_enabled = False
    top_n = 16

    if request.method == "POST":
        user_id = request.form.get("user_id")
        if user_id:
            selected_user = int(user_id)
        selected_algorithms = request.form.getlist("algorithms") or [request.form.get("algorithm", "cosine")]
        selected_algorithms = [algo for algo in selected_algorithms if algo]
        if not selected_algorithms:
            selected_algorithms = ["cosine"]
        selected_algorithms = selected_algorithms[:4]

        top_n_value = request.form.get("top_n")
        if top_n_value:
            try:
                top_n = int(top_n_value)
            except ValueError:
                top_n = 16
        top_n = max(4, min(top_n, 40))

        blend_weight = int(request.form.get("blend_weight", blend_weight))
        blend_enabled = request.form.get("blend_enabled") == "1"

        if selected_user is not None:
            for algo in selected_algorithms:
                recommendations = recommender.recommend_with_ids(selected_user, algorithm=algo, top_n=top_n)
                algo_results[algo] = [
                    {
                        "movie_id": movie_id,
                        "title": title,
                        "score": round(score, 4),
                    }
                    for movie_id, title, score in recommendations
                ]

            if blend_enabled and len(selected_algorithms) >= 2:
                blended_results = _blend_algorithm_scores(
                    selected_algorithms, algo_results, blend_weight, top_n
                )

    if not selected_algorithms:
        selected_algorithms = ["cosine"]

    primary_algorithm = selected_algorithms[0]
    secondary_algorithms = selected_algorithms[1:]
    normalized_weight = max(0, min(blend_weight, 100))
    blend_summary = {
        "primary_key": primary_algorithm,
        "primary_label": ALGORITHM_NAMES.get(primary_algorithm, primary_algorithm),
        "secondary_keys": secondary_algorithms,
        "primary_share": 100 - normalized_weight,
        "secondary_share": normalized_weight,
    }

    return render_template(
        "recommend.html",
        users=recommender.selected_users,
        algorithms=ALGORITHM_NAMES,
        algo_results=algo_results,
        blended_results=blended_results,
        blend_enabled=blend_enabled,
        blend_weight=blend_weight,
        blend_summary=blend_summary,
        selected_algorithms=selected_algorithms,
        selected_user=selected_user,
        top_n=top_n,
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


@app.route("/api/node/<node_id>")
def node_metadata(node_id: str):
    profile = recommender.node_profile(node_id)
    if not profile:
        return jsonify({"error": "Node not found"}), 404
    return jsonify(profile)


if __name__ == "__main__":
    app.run(debug=True)
