# 🧬 SmartShop GA — Genetic Algorithm Recommendation System

> A full-stack web application that uses **Genetic Algorithms** to optimize product recommendations in an e-commerce store.

---

## 👥 Team Members

| # | Name | ID |
|---|------|----|
| 1 |      |    |
| 2 |      |    |
| 3 |      |    |
| 4 |      |    |
| 5 |      |    |

---

## 📌 Project Overview

This project implements a **Genetic Algorithm (GA)** for personalized product recommendation optimization, based on real user behavior and rating data.

### Problem Solved
> **Optimizing e-commerce recommendations** — finding the best set of products to show each user, maximizing click-through rate and purchases.

---

## 📄 Scientific Reference

**Paper:** *"Genetic Algorithm-Based Collaborative Filtering for E-Commerce Recommendation Systems"*  
**Year:** 2024–2025  
**Source:** IEEE Xplore / Springer  
*(Replace with your actual paper citation)*

---

## 🧬 How the Genetic Algorithm Works

```
Population Init → Fitness Evaluation → Selection → Crossover → Mutation → Repeat
```

| Step | Description |
|------|-------------|
| **Chromosome** | A list of N product IDs = one recommendation set |
| **Population** | 40 different recommendation sets |
| **Fitness** | User rating score + behavior score + diversity bonus |
| **Selection** | Elitism: top 20% survive |
| **Crossover** | Single-point crossover between two parents |
| **Mutation** | 15% chance to replace a product randomly |
| **Termination** | After N generations (20–150, user-controlled) |

### Fitness Function
```
fitness(chromosome) = Σ score(user, product) + categories_diversity × 0.15

score(user, product) = rating/5  +  viewed×0.1 + clicked×0.3 + purchased×1.0
```

---

## 📂 Dataset — HW__Data_S25

| File | Records | Columns |
|------|---------|---------|
| `users.xlsx` | 1,000 | user_id, age, country |
| `products.xlsx` | 500 | product_id, category, price |
| `ratings.xlsx` | 5,000 | user_id, product_id, rating (1-5) |
| `behavior_15500.xlsx` | 13,500 | user_id, product_id, viewed, clicked, purchased |

---

## 🚀 Installation & Run

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/SmartShop-GA.git
cd SmartShop-GA

# 2. Install dependencies
pip install -r requirements.txt

# 3. Place data files in /data folder

# 4. Run the app
python app.py

# 5. Open browser
http://localhost:5000
```

---

## 🛠️ Tech Stack

- **Backend:** Python, Flask
- **Algorithm:** Custom Genetic Algorithm (NumPy)
- **Frontend:** HTML5, CSS3, Vanilla JS (RTL Arabic UI)
- **Data:** Pandas, OpenPyXL
- **Charts:** Canvas API

---

## 📁 Project Structure

```
SmartShop-GA/
├── app.py                  # Flask server + GA engine
├── templates/
│   └── index.html          # Full UI (RTL Arabic)
├── data/
│   ├── users.xlsx
│   ├── products.xlsx
│   ├── ratings.xlsx
│   └── behavior_15500.xlsx
├── requirements.txt
├── Report.md               # Technical report (Arabic)
└── README.md
```

---

## 📸 Features

- 🎯 Real-time GA recommendation generation
- 📈 Live fitness evolution chart
- 👤 Per-user personalization (1,000 users)
- 📦 6-category product diversity
- 📊 Dataset statistics dashboard
- 🌙 Dark mode Arabic RTL interface
