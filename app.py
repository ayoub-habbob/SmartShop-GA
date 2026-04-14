from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
import random
import os

app = Flask(__name__)

# ─── Load Data ────────────────────────────────────────────────────────────────
BASE = os.path.join(os.path.dirname(__file__), "data")
users_df    = pd.read_excel(os.path.join(BASE, "users.xlsx"))
products_df = pd.read_excel(os.path.join(BASE, "products.xlsx"))
ratings_df  = pd.read_excel(os.path.join(BASE, "ratings.xlsx"))
behavior_df = pd.read_excel(os.path.join(BASE, "behavior_15500.xlsx"))

ALL_PRODUCTS = products_df["product_id"].tolist()
CATEGORIES   = sorted(products_df["category"].unique().tolist())

# ─── Score Matrix ─────────────────────────────────────────────────────────────
def build_score_matrix():
    r = ratings_df.copy()
    r["score"] = r["rating"] / 5.0
    b = behavior_df.copy()
    b["score"] = b["viewed"]*0.1 + b["clicked"]*0.3 + b["purchased"]*1.0
    combined = pd.concat([
        r[["user_id","product_id","score"]],
        b[["user_id","product_id","score"]]
    ]).groupby(["user_id","product_id"])["score"].sum().reset_index()
    return combined.pivot(index="user_id", columns="product_id", values="score").fillna(0)

SCORE_MATRIX = build_score_matrix()

# ─── Step 1: Build User Profile ───────────────────────────────────────────────
def build_user_profile(user_id):
    profile = {
        "top_viewed_cats":    [],
        "top_clicked_cats":   [],
        "top_purchased_cats": [],
        "avg_rating_per_cat": {},
        "price_min":  0,
        "price_max":  9999,
        "price_avg":  500,
        "purchased_products": [],
        "fav_categories":     [],
    }

    user_beh = behavior_df[behavior_df["user_id"] == user_id]
    if not user_beh.empty:
        user_beh = user_beh.merge(
            products_df[["product_id","category","price"]], on="product_id", how="left")

        viewed = user_beh[user_beh["viewed"] == 1]
        if not viewed.empty:
            profile["top_viewed_cats"] = (
                viewed.groupby("category")["viewed"].sum()
                .sort_values(ascending=False).head(3).index.tolist())

        clicked = user_beh[user_beh["clicked"] == 1]
        if not clicked.empty:
            profile["top_clicked_cats"] = (
                clicked.groupby("category")["clicked"].sum()
                .sort_values(ascending=False).head(3).index.tolist())

        purchased = user_beh[user_beh["purchased"] == 1]
        if not purchased.empty:
            profile["top_purchased_cats"] = (
                purchased.groupby("category")["purchased"].sum()
                .sort_values(ascending=False).head(3).index.tolist())
            profile["purchased_products"] = purchased["product_id"].tolist()

        interacted = user_beh[(user_beh["viewed"]==1)|(user_beh["clicked"]==1)]
        if not interacted.empty:
            prices = interacted["price"].dropna()
            if len(prices) > 0:
                profile["price_min"] = float(prices.quantile(0.1))
                profile["price_max"] = float(prices.quantile(0.9))
                profile["price_avg"] = float(prices.mean())

    user_rat = ratings_df[ratings_df["user_id"] == user_id]
    if not user_rat.empty:
        user_rat = user_rat.merge(
            products_df[["product_id","category"]], on="product_id", how="left")
        profile["avg_rating_per_cat"] = (
            user_rat.groupby("category")["rating"].mean().round(2).to_dict())

    fav_score = {}
    for cat in profile["top_purchased_cats"]:
        fav_score[cat] = fav_score.get(cat, 0) + 3
    for cat in profile["top_clicked_cats"]:
        fav_score[cat] = fav_score.get(cat, 0) + 2
    for cat in profile["top_viewed_cats"]:
        fav_score[cat] = fav_score.get(cat, 0) + 1
    for cat, avg in profile["avg_rating_per_cat"].items():
        if avg >= 4.0:
            fav_score[cat] = fav_score.get(cat, 0) + 2

    profile["fav_categories"] = sorted(fav_score, key=fav_score.get, reverse=True)
    return profile

# ─── Step 2: Initial Recommendation ──────────────────────────────────────────
def initial_recommendation(user_id, profile, n=50):
    purchased = set(profile["purchased_products"])
    fav_cats  = profile["fav_categories"]
    p_min     = profile["price_min"] * 0.5
    p_max     = profile["price_max"] * 1.5

    candidates = products_df.copy()
    candidates = candidates[~candidates["product_id"].isin(purchased)]

    if p_max > p_min:
        candidates = candidates[
            (candidates["price"] >= p_min) &
            (candidates["price"] <= p_max)]

    if fav_cats:
        candidates = candidates.copy()
        candidates["priority"] = candidates["category"].apply(
            lambda c: fav_cats.index(c) if c in fav_cats else len(fav_cats))
        candidates = candidates.sort_values("priority")

    result = candidates.head(n)["product_id"].tolist()
    if len(result) < n:
        remaining = [p for p in ALL_PRODUCTS if p not in result and p not in purchased]
        result += remaining[:n - len(result)]

    return result if result else ALL_PRODUCTS[:n]

# ─── Step 3: Genetic Algorithm ────────────────────────────────────────────────
class GeneticRecommender:
    def __init__(self, user_id, candidates, profile,
                 n_recs=6, pop_size=40, generations=60, mutation_rate=0.15):
        self.user_id       = user_id
        self.candidates    = candidates
        self.profile       = profile
        self.n_recs        = n_recs
        self.pop_size      = pop_size
        self.generations   = generations
        self.mutation_rate = mutation_rate

    def _fitness(self, chromosome):
        total = 0.0
        for pid in chromosome:
            if self.user_id in SCORE_MATRIX.index and pid in SCORE_MATRIX.columns:
                total += SCORE_MATRIX.loc[self.user_id, pid]

            cat_s = products_df.loc[products_df["product_id"]==pid, "category"]
            if not cat_s.empty:
                cat = cat_s.values[0]
                fav = self.profile["fav_categories"]
                if fav and cat in fav:
                    total += (len(fav) - fav.index(cat)) * 0.1
                avg_r = self.profile["avg_rating_per_cat"].get(cat, 3.0)
                if avg_r >= 4.0:
                    total += 0.2
                elif avg_r < 2.0:
                    total -= 0.1

            if pid in self.profile["purchased_products"]:
                total -= 0.5

        cats = products_df[products_df["product_id"].isin(chromosome)]["category"].nunique()
        total += cats * 0.15
        return total

    def _init_population(self):
        pool = self.candidates if len(self.candidates) >= self.n_recs else ALL_PRODUCTS
        return [random.sample(pool, min(self.n_recs, len(pool)))
                for _ in range(self.pop_size)]

    def _crossover(self, p1, p2):
        point = random.randint(1, self.n_recs - 1)
        child = p1[:point]
        for gene in p2:
            if gene not in child:
                child.append(gene)
            if len(child) == self.n_recs:
                break
        pool = self.candidates if self.candidates else ALL_PRODUCTS
        for pid in pool:
            if pid not in child:
                child.append(pid)
            if len(child) == self.n_recs:
                break
        return child[:self.n_recs]

    def _mutate(self, chromosome):
        chrom = chromosome[:]
        pool  = self.candidates if self.candidates else ALL_PRODUCTS
        for i in range(len(chrom)):
            if random.random() < self.mutation_rate:
                new_gene = random.choice(pool)
                if new_gene not in chrom:
                    chrom[i] = new_gene
        return chrom

    def run(self):
        population = self._init_population()
        fitness_history = []
        for gen in range(self.generations):
            scored = sorted([(self._fitness(c), c) for c in population],
                            key=lambda x: x[0], reverse=True)
            fitness_history.append(round(scored[0][0], 4))
            elite_n = max(2, self.pop_size // 5)
            new_pop = [c for _, c in scored[:elite_n]]
            while len(new_pop) < self.pop_size:
                p1, p2 = random.sample([c for _,c in scored[:self.pop_size//2]], 2)
                new_pop.append(self._mutate(self._crossover(p1, p2)))
            population = new_pop
        return scored[0][1], fitness_history

# ─── Routes ───────────────────────────────────────────────────────────────────
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

    # الخطوة 1: ملف المستخدم
    profile = build_user_profile(user_id)
    # الخطوة 2: التوصية الأولية
    candidates = initial_recommendation(user_id, profile, n=50)
    # الخطوة 3: الخوارزمية الجينية
    ga = GeneticRecommender(user_id, candidates, profile,
                            n_recs=n_recs, generations=gens)
    best_products, fitness_history = ga.run()

    recs = []
    for pid in best_products:
        row   = products_df[products_df["product_id"] == pid].iloc[0]
        avg_r = ratings_df[ratings_df["product_id"]==pid]["rating"].mean()
        recs.append({
            "product_id": int(pid),
            "category":   row["category"],
            "price":      int(row["price"]),
            "avg_rating": round(float(avg_r), 1) if not np.isnan(avg_r) else 3.5,
        })

    user_info = users_df[users_df["user_id"]==user_id].iloc[0]
    return jsonify({
        "recommendations": recs,
        "fitness_history": fitness_history,
        "user": {"user_id": user_id,
                 "age":     int(user_info["age"]),
                 "country": user_info["country"]},
        "user_profile": {
            "fav_categories":     profile["fav_categories"][:4],
            "top_purchased_cats": profile["top_purchased_cats"],
            "top_clicked_cats":   profile["top_clicked_cats"],
            "price_range": f"{int(profile['price_min'])} - {int(profile['price_max'])}",
            "purchased_count":  len(profile["purchased_products"]),
            "candidates_count": len(candidates),
        },
        "generations_run": gens
    })

@app.route("/stats")
def stats():
    return jsonify({
        "categories":      products_df["category"].value_counts().to_dict(),
        "countries":       users_df["country"].value_counts().head(8).to_dict(),
        "rating_dist":     ratings_df["rating"].value_counts().sort_index().to_dict(),
        "behavior_summary": {
            "total_views":     int(behavior_df["viewed"].sum()),
            "total_clicks":    int(behavior_df["clicked"].sum()),
            "total_purchases": int(behavior_df["purchased"].sum())
        }
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
