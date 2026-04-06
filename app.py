from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
import random
import json
import os

app = Flask(__name__)

# ─── Load Data ───────────────────────────────────────────────────────────────
BASE = os.path.join(os.path.dirname(__file__), "data")
users_df    = pd.read_excel(os.path.join(BASE, "users.xlsx"))
products_df = pd.read_excel(os.path.join(BASE, "products.xlsx"))
ratings_df  = pd.read_excel(os.path.join(BASE, "ratings.xlsx"))
behavior_df = pd.read_excel(os.path.join(BASE, "behavior_15500.xlsx"))

# Pre-compute user-product score matrix (rating + behavior signals)
def build_score_matrix():
    # Normalize ratings to 0-1
    r = ratings_df.copy()
    r["score"] = r["rating"] / 5.0

    # Behavior score: viewed=0.1, clicked=0.3, purchased=1.0
    b = behavior_df.copy()
    b["score"] = b["viewed"]*0.1 + b["clicked"]*0.3 + b["purchased"]*1.0

    combined = pd.concat([
        r[["user_id","product_id","score"]],
        b[["user_id","product_id","score"]]
    ]).groupby(["user_id","product_id"])["score"].sum().reset_index()

    matrix = combined.pivot(index="user_id", columns="product_id", values="score").fillna(0)
    return matrix

SCORE_MATRIX = build_score_matrix()

ALL_PRODUCTS = products_df["product_id"].tolist()
CATEGORIES   = sorted(products_df["category"].unique().tolist())

# ─── Genetic Algorithm ────────────────────────────────────────────────────────
class GeneticRecommender:
    def __init__(self, user_id, n_recs=6, pop_size=40, generations=60, mutation_rate=0.15):
        self.user_id       = user_id
        self.n_recs        = n_recs
        self.pop_size      = pop_size
        self.generations   = generations
        self.mutation_rate = mutation_rate
        self.history       = []

    def _fitness(self, chromosome):
        """Score a list of product_ids for this user."""
        total = 0.0
        for pid in chromosome:
            if self.user_id in SCORE_MATRIX.index and pid in SCORE_MATRIX.columns:
                total += SCORE_MATRIX.loc[self.user_id, pid]
            # Diversity bonus: reward different categories
        cats = products_df[products_df["product_id"].isin(chromosome)]["category"].nunique()
        diversity_bonus = cats * 0.15
        return total + diversity_bonus

    def _init_population(self):
        pop = []
        for _ in range(self.pop_size):
            chrom = random.sample(ALL_PRODUCTS, self.n_recs)
            pop.append(chrom)
        return pop

    def _crossover(self, p1, p2):
        point = random.randint(1, self.n_recs - 1)
        child = p1[:point]
        for gene in p2:
            if gene not in child:
                child.append(gene)
            if len(child) == self.n_recs:
                break
        # fill if needed
        for pid in ALL_PRODUCTS:
            if pid not in child:
                child.append(pid)
            if len(child) == self.n_recs:
                break
        return child[:self.n_recs]

    def _mutate(self, chromosome):
        chrom = chromosome[:]
        for i in range(len(chrom)):
            if random.random() < self.mutation_rate:
                new_gene = random.choice(ALL_PRODUCTS)
                if new_gene not in chrom:
                    chrom[i] = new_gene
        return chrom

    def run(self):
        population = self._init_population()
        best_fitness_per_gen = []

        for gen in range(self.generations):
            scored = [(self._fitness(c), c) for c in population]
            scored.sort(key=lambda x: x[0], reverse=True)
            best_fitness_per_gen.append(round(scored[0][0], 4))

            # Elitism: keep top 20%
            elite_n = max(2, self.pop_size // 5)
            new_pop  = [c for _, c in scored[:elite_n]]

            # Fill rest via crossover + mutation
            while len(new_pop) < self.pop_size:
                p1, p2 = random.sample([c for _, c in scored[:self.pop_size//2]], 2)
                child  = self._crossover(p1, p2)
                child  = self._mutate(child)
                new_pop.append(child)

            population = new_pop
            self.history = best_fitness_per_gen

        best = scored[0][1]
        return best, best_fitness_per_gen

# ─── Routes ──────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    user_list = users_df[["user_id","age","country"]].to_dict("records")
    return render_template("index.html",
                           users=user_list,
                           categories=CATEGORIES,
                           total_users=len(users_df),
                           total_products=len(products_df),
                           total_ratings=len(ratings_df),
                           total_behaviors=len(behavior_df))

@app.route("/recommend", methods=["POST"])
def recommend():
    data    = request.get_json()
    user_id = int(data.get("user_id", 1))
    n_recs  = int(data.get("n_recs", 6))
    gens    = int(data.get("generations", 60))

    ga = GeneticRecommender(user_id, n_recs=n_recs, generations=gens)
    best_products, fitness_history = ga.run()

    # Build result
    recs = []
    for pid in best_products:
        row = products_df[products_df["product_id"] == pid].iloc[0]
        # Get user rating if exists
        user_ratings = ratings_df[(ratings_df["user_id"]==user_id) & (ratings_df["product_id"]==pid)]
        rating = int(user_ratings["rating"].values[0]) if len(user_ratings) > 0 else None
        # Get avg rating
        avg_r = ratings_df[ratings_df["product_id"]==pid]["rating"].mean()
        recs.append({
            "product_id": int(pid),
            "category":   row["category"],
            "price":      int(row["price"]),
            "avg_rating": round(float(avg_r), 1) if not np.isnan(avg_r) else 3.5,
            "user_rating": rating
        })

    user_info = users_df[users_df["user_id"]==user_id].iloc[0]

    return jsonify({
        "recommendations": recs,
        "fitness_history":  fitness_history,
        "user": {
            "user_id": user_id,
            "age":     int(user_info["age"]),
            "country": user_info["country"]
        },
        "generations_run": gens
    })

@app.route("/stats")
def stats():
    cat_counts = products_df["category"].value_counts().to_dict()
    country_counts = users_df["country"].value_counts().head(8).to_dict()
    rating_dist = ratings_df["rating"].value_counts().sort_index().to_dict()
    behavior_summary = {
        "total_views":     int(behavior_df["viewed"].sum()),
        "total_clicks":    int(behavior_df["clicked"].sum()),
        "total_purchases": int(behavior_df["purchased"].sum())
    }
    return jsonify({
        "categories":        cat_counts,
        "countries":         country_counts,
        "rating_dist":       rating_dist,
        "behavior_summary":  behavior_summary
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
