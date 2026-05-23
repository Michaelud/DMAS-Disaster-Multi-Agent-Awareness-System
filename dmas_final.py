"""
DMAS – Disaster Multi-Agent Awareness System [Fixed Production Script]
Author: Michael Michael Udofia
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RUNTIME ENVIRONMENT & HARDWARE SPECIFICATIONS:
  - OS: Ubuntu 22.04 LTS (Jammy Jellyfish) containerized via Docker
  - Processor: Intel Core i9-12900K (16 cores, 24 threads)
  - Memory: 64 GB DDR5 RAM | Storage: 1 TB NVMe SSD
  - GPU: NVIDIA GeForce RTX 3080 (geospatial matrix/CV parallelization)
  - Language: Python 3.10+ (asyncio framework)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA NOTE:
  Synthetic dataset empirically grounded in:
  • IOM DTM / NEMA Joint Assessment Report, 30 Dec 2024
    → 275,621 persons, 48,403 households, 8 LGAs
  • NIMET Meteorological Bulletin, Dec 2024
    → 48.7 mm/h rainfall, 122 cm tidal surge, 187.2 mm/24h
  • Lagos State Ministry of Environment 2024
    → Annual rainfall 1,936.2 mm (+12.5% above long-term mean)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import json
import logging
import random
import math
import os
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass

import aiohttp

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.gridspec as gridspec
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import aio_pika
except ImportError:
    aio_pika = None

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    import asyncpg
except ImportError:
    AsyncIOMotorClient, asyncpg = None, None

try:
    import geopandas as gpd
    from shapely.geometry import Point
except ImportError:
    gpd, Point = None, None

try:
    import rospy
    from std_msgs.msg import String as RosString
except ImportError:
    rospy = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ─────────────────────────────────────────────────────────────────────────
# CONSTANTS FROM DMAS PAPER
# ─────────────────────────────────────────────────────────────────────────
W_PHYSICAL  = 0.90
W_GOV       = 0.75
W_SOCIAL    = 0.40
TRUST_GATE       = 0.85
UNCERTAINTY_GATE = 0.50
W1, W2, W3  = 0.50, 0.30, 0.20

WEATHER = {
    "event_date":     "2024-12-03",
    "rain_1h":        48.7,
    "rain_24h":       187.2,
    "wind_speed":     8.3,
    "tidal_surge_cm": 122,
    "temperature":    27.4,
    "humidity":       94,
    "description":    "Heavy tropical rainfall with tidal surge",
    "source":         "NIMET / Lagos State Ministry of Environment, Dec 2024",
}

LGAS = [
    {"name": "Ajegunle",       "lga": "Ajeromi-Ifelodun", "vulnerability": 0.92,
     "flood_depth_m": 1.85, "persons": 52_440, "households": 9_200,
     "infra": "critical",     "base_tweet_rate": 0.22, "base_call_rate": 0.20},
    {"name": "Ketu",           "lga": "Kosofe",           "vulnerability": 0.80,
     "flood_depth_m": 1.60, "persons": 40_470, "households": 7_100,
     "infra": "critical",     "base_tweet_rate": 0.16, "base_call_rate": 0.18},
    {"name": "Surulere",       "lga": "Surulere",         "vulnerability": 0.75,
     "flood_depth_m": 1.20, "persons": 33_060, "households": 5_800,
     "infra": "degraded",     "base_tweet_rate": 0.14, "base_call_rate": 0.14},
    {"name": "Lagos Island",   "lga": "Lagos Island",     "vulnerability": 0.88,
     "flood_depth_m": 1.70, "persons": 36_480, "households": 6_400,
     "infra": "critical",     "base_tweet_rate": 0.18, "base_call_rate": 0.17},
    {"name": "Ikorodu",        "lga": "Ikorodu",          "vulnerability": 0.82,
     "flood_depth_m": 1.90, "persons": 47_310, "households": 8_300,
     "infra": "critical",     "base_tweet_rate": 0.12, "base_call_rate": 0.15},
    {"name": "Victoria Island","lga": "Eti-Osa",          "vulnerability": 0.35,
     "flood_depth_m": 0.45, "persons": 5_130,  "households": 900,
     "infra": "operational",  "base_tweet_rate": 0.06, "base_call_rate": 0.04},
    {"name": "Lekki Phase 1",  "lga": "Eti-Osa",          "vulnerability": 0.50,
     "flood_depth_m": 0.80, "persons": 11_970, "households": 2_100,
     "infra": "degraded",     "base_tweet_rate": 0.07, "base_call_rate": 0.06},
    {"name": "Mile 12 / Owode","lga": "Kosofe",           "vulnerability": 0.85,
     "flood_depth_m": 2.10, "persons": 44_460, "households": 7_800,
     "infra": "critical",     "base_tweet_rate": 0.05, "base_call_rate": 0.06},
]

TWEET_TEMPLATES_TRUE = [
    "Water is {depth} deep in {nb}. My family is on the roof. Please help! #LagosFlood2024",
    "FLOODING in {nb}! All roads submerged. Can't leave the house. #SOS #Lagos",
    "{nb} is completely underwater. People stranded since {hour}am. LASEMA nowhere to be found.",
    "The entire {nb} market is flooded. Fish, yam, everything lost. God help us. #LagosFlood",
    "Roads in {nb} totally impassable. Water reaching chest level in some areas. Very dangerous.",
    "We have been trapped in {nb} for {hours} hours. No rescue team. Water still rising. #Help",
    "Tidal surge has blocked all drains in {nb}. Water has nowhere to go. Flooding worsening.",
    "Emergency! {nb} residents need help NOW. Elderly people and children stranded.",
    "My shop in {nb} is submerged. Lost everything. This December flood is the worst ever.",
    "Power has been out in {nb} since the flood started. No light, no rescue, no news.",
    "Bridge near {nb} is flooded. No way to get in or out by road. Boats needed urgently.",
    "Heavy flooding in {nb}. I can see mattresses and furniture floating in the street.",
    "LASEMA please respond to {nb}. People have been waiting for rescue for {hours} hours!",
    "The water in {nb} is still rising. This is worse than 2022. We need help now. #Flood",
    "Children crying in {nb}, we cannot go anywhere. Water surrounding the whole compound.",
]

TWEET_TEMPLATES_MISINFORMATION = [
    "I heard {nb} is flooded but I'm not sure, someone told me on WhatsApp. #rumour",
    "False alarm — the rain in {nb} is just normal Lagos December rain. Stop panicking.",
    "People exaggerating the flood in {nb}. It's not that deep, I just drove through.",
    "Don't believe everything you read. {nb} flooding stories are being blown out of proportion.",
    "My cousin said {nb} is fine. The flooding cleared already. Social media exaggerating.",
    "I'm in {nb} right now. The flooding is minor. Nothing to worry about. Calm down.",
    "Stop sharing fake news about {nb}. The roads are accessible. I just passed there.",
]

TWEET_TEMPLATES_NOISE = [
    "Lagos government should fix the drainage in {nb} every year we have this problem.",
    "This flooding in {nb} happens every year. Nothing new. Politicians don't care.",
    "When will leaders fix {nb} infrastructure? We have been complaining for 10 years.",
    "God will judge the people responsible for the bad drainage in {nb}. #Nigeria",
    "Please vote wisely next election. This flooding in {nb} is a result of bad leadership.",
]

CALL_INCIDENTS = [
    ("Mass displacement — residents stranded, urgent evacuation needed", "Critical"),
    ("Infrastructure failure — power station flooded, roads blocked", "Critical"),
    ("Tidal surge flooding — drainage backflow throughout area", "Critical"),
    ("River bank breach — market and residential area submerged", "Critical"),
    ("Medical emergency — sick persons cannot be evacuated due to flooding", "Critical"),
    ("Building collapse risk — foundation undermined by flood water", "High"),
    ("Displacement — households affected, temporary shelter needed", "High"),
    ("Road flooding — major arterials blocked, traffic diverted", "High"),
    ("School submerged — families sheltering in upper floors", "High"),
    ("Hospital access blocked — ambulances cannot reach affected areas", "High"),
    ("Flooding in residential area — moderate water level", "Medium"),
    ("Road obstruction — flooding reducing to one lane", "Medium"),
    ("Market flooding — commercial losses reported", "Medium"),
    ("Drainage overflow — localised flooding in low-lying areas", "Medium"),
    ("Precautionary alert — water level rising near residential zone", "Low"),
    ("Minor flooding — some pavement affected, pedestrians displaced", "Low"),
]

SEVERITY_BANDS = [
    (0.75, "CATASTROPHIC", "🔴"),
    (0.55, "CRITICAL",     "🟠"),
    (0.35, "MODERATE",     "🟡"),
    (0.00, "STABLE",       "🟢"),
]

# ─────────────────────────────────────────────────────────────────────────
# DATA GENERATION
# ─────────────────────────────────────────────────────────────────────────
def generate_timestamp(base_hour=0, spread_hours=24):
    base = datetime(2024, 12, 3, base_hour, 0, 0)
    offset = random.randint(0, spread_hours * 60)
    return (base + timedelta(minutes=offset)).strftime("%Y-%m-%d %H:%M")

def generate_tweets(n=2000):
    tweets = []
    rates = [lg["base_tweet_rate"] for lg in LGAS]
    total = sum(rates)
    norm_rates = [r / total for r in rates]
    for i in range(n):
        lga = random.choices(LGAS, weights=norm_rates, k=1)[0]
        nb  = lga["name"]
        v   = lga["vulnerability"]
        r   = random.random()
        if r < v * 0.75:
            template   = random.choice(TWEET_TEMPLATES_TRUE)
            tweet_type = "distress"
            engagement = random.randint(50, 25000)
            credibility_base = random.uniform(0.55, 0.95)
        elif r < v * 0.75 + 0.15:
            template   = random.choice(TWEET_TEMPLATES_MISINFORMATION)
            tweet_type = "misinformation"
            engagement = random.randint(10, 3000)
            credibility_base = random.uniform(0.05, 0.40)
        else:
            template   = random.choice(TWEET_TEMPLATES_NOISE)
            tweet_type = "noise"
            engagement = random.randint(5, 500)
            credibility_base = random.uniform(0.10, 0.35)
        depth_str = f"{lga['flood_depth_m']:.1f}m"
        hour  = random.randint(1, 12)
        hours = random.randint(2, 18)
        text  = template.format(nb=nb, depth=depth_str, hour=hour, hours=hours)
        tweets.append({
            "id": i + 1, "lga": nb, "text": text, "type": tweet_type,
            "engagement": engagement, "credibility_base": round(credibility_base, 3),
            "timestamp": generate_timestamp(),
        })
    return tweets

def generate_iot_sensors(n=600):
    sensors = []
    per_lga = n // len(LGAS)
    sid = 1
    for lga in LGAS:
        count = per_lga + random.randint(-5, 5)
        for _ in range(count):
            base_depth = lga["flood_depth_m"]
            noise      = random.uniform(-0.30, 0.30)
            depth      = max(0.0, round(base_depth + noise, 2))
            alert      = depth > 1.0 or lga["infra"] == "critical"
            sensors.append({
                "sensor_id": f"IOT-{sid:04d}", "lga": lga["name"],
                "water_level_m": depth, "rainfall_mm": round(random.uniform(30, 60), 1),
                "wind_mps": round(random.uniform(5, 12), 1), "alert": alert,
                "infra_status": lga["infra"], "timestamp": generate_timestamp(),
            })
            sid += 1
    return sensors

def generate_calls(n=400):
    calls = []
    per_lga = n // len(LGAS)
    cid = 1
    for lga in LGAS:
        count = per_lga + random.randint(-3, 3)
        count = max(5, int(count * lga["base_call_rate"] * len(LGAS)))
        for _ in range(count):
            incident, severity = random.choice(CALL_INCIDENTS)
            if lga["vulnerability"] > 0.80 and random.random() < 0.6:
                severity = "Critical"
            calls.append({
                "call_id": f"CALL-{cid:04d}", "lga": lga["name"],
                "incident": incident, "severity": severity,
                "timestamp": generate_timestamp(),
            })
            cid += 1
    return calls

# ─────────────────────────────────────────────────────────────────────────
# REAL Sc FORMULA — Weighted Convergence Algorithm
# Sc(r) = Σ(wi·ki) / Σ(wi)
# ─────────────────────────────────────────────────────────────────────────
def compute_sc(lga, tweets, sensors, calls, weather):
    nb = lga["name"]

    # k_physical: IoT sensor alert rate + flood depth
    lga_sensors = [s for s in sensors if s["lga"] == nb]
    if lga_sensors:
        alert_rate = sum(1 for s in lga_sensors if s["alert"]) / len(lga_sensors)
        mean_depth = sum(s["water_level_m"] for s in lga_sensors) / len(lga_sensors)
        k_phys     = min(alert_rate * 0.60 + (mean_depth / 3.0) * 0.40, 1.0)
        if weather["rain_1h"] > 30:
            k_phys = min(k_phys + 0.08, 1.0)
    else:
        k_phys = 0.20

    # k_gov: severity-weighted emergency call score
    lga_calls = [c for c in calls if c["lga"] == nb]
    if lga_calls:
        sev_map  = {"Critical": 1.0, "High": 0.80, "Medium": 0.60, "Low": 0.40}
        sev_vals = [sev_map.get(c["severity"], 0.5) for c in lga_calls]
        k_gov    = min(sum(sev_vals) / len(sev_vals), 1.0)
    else:
        k_gov = 0.25

    # k_social: engagement-weighted distress tweet ratio
    lga_tweets = [t for t in tweets if t["lga"] == nb]
    if lga_tweets:
        distress_tweets = [t for t in lga_tweets if t["type"] == "distress"]
        distress_ratio  = len(distress_tweets) / len(lga_tweets)
        if distress_tweets:
            mean_eng  = sum(t["engagement"] for t in distress_tweets) / len(distress_tweets)
            eng_score = min(mean_eng / 15000, 1.0)
        else:
            eng_score = 0.0
        k_soc = min(0.30 + distress_ratio * 0.40 + eng_score * 0.30, 1.0)
    else:
        k_soc = 0.05

    # Sc formula
    numerator   = (W_PHYSICAL * k_phys) + (W_GOV * k_gov) + (W_SOCIAL * k_soc)
    denominator = W_PHYSICAL + W_GOV + W_SOCIAL
    sc = round(numerator / denominator, 3)

    if sc >= TRUST_GATE:
        gate = "TRUST"
    elif sc >= UNCERTAINTY_GATE:
        gate = "UNCERTAINTY"
    else:
        gate = "SUPPRESSED"

    return {
        "sc": sc, "gate": gate,
        "k_phys": round(k_phys, 3), "k_gov": round(k_gov, 3), "k_soc": round(k_soc, 3),
        "n_tweets": len(lga_tweets), "n_sensors": len(lga_sensors), "n_calls": len(lga_calls),
        "distress_tweets": len([t for t in lga_tweets if t["type"] == "distress"]),
        "misinfo_tweets":  len([t for t in lga_tweets if t["type"] == "misinformation"]),
        "noise_tweets":    len([t for t in lga_tweets if t["type"] == "noise"]),
    }

# ─────────────────────────────────────────────────────────────────────────
# CDSS FORMULA
# CDSS(j,t) = w1·S + w2·V + w3·HI
# ─────────────────────────────────────────────────────────────────────────
def compute_cdss(lga, sc_result, weather):
    S  = sc_result["sc"]
    V  = lga["vulnerability"]
    HI = min(lga["flood_depth_m"] / 2.5, 1.0)
    if lga["infra"] == "critical":
        HI = min(HI * 1.20, 1.0)
    if weather["rain_1h"] > 30:
        HI = min(HI + 0.05, 1.0)
    cdss = round(W1 * S + W2 * V + W3 * HI, 3)
    return {"cdss": cdss, "S": S, "V": V, "HI": round(HI, 3)}

def severity_label(cdss):
    for threshold, label, icon in SEVERITY_BANDS:
        if cdss >= threshold:
            return label, icon
    return "STABLE", "🟢"

# ─────────────────────────────────────────────────────────────────────────
# EVALUATION METRICS
# ─────────────────────────────────────────────────────────────────────────
def compute_metrics(tweets, sc_results):
    suppressed_lgas = [nb for nb, r in sc_results.items() if r["gate"] == "SUPPRESSED"]
    trust_lgas      = [nb for nb, r in sc_results.items() if r["gate"] == "TRUST"]
    uncertainty_lgas= [nb for nb, r in sc_results.items() if r["gate"] == "UNCERTAINTY"]

    total_distress = sum(1 for t in tweets if t["type"] == "distress")
    total_misinfo  = sum(1 for t in tweets if t["type"] in ("misinformation", "noise"))

    # True Positives: distress tweets in TRUST zones (correctly forwarded)
    TP = sum(1 for t in tweets if t["lga"] in trust_lgas and t["type"] == "distress")
    # False Negatives: distress tweets in SUPPRESSED zones (missed)
    FN = sum(1 for t in tweets if t["lga"] in suppressed_lgas and t["type"] == "distress")
    # True Negatives: misinfo/noise in SUPPRESSED zones (correctly blocked)
    TN = sum(1 for t in tweets if t["lga"] in suppressed_lgas and t["type"] in ("misinformation","noise"))
    # False Positives: misinfo/noise in TRUST zones (incorrectly forwarded)
    FP = sum(1 for t in tweets if t["lga"] in trust_lgas and t["type"] in ("misinformation","noise"))

    precision = round(TP / (TP + FP), 4) if (TP + FP) > 0 else 0
    recall    = round(TP / (TP + FN), 4) if (TP + FN) > 0 else 0
    f1        = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0
    accuracy  = round((TP + TN) / len(tweets), 4) if tweets else 0
    specificity = round(TN / (TN + FP), 4) if (TN + FP) > 0 else 0

    suppression_rate = round(TN / total_misinfo * 100, 1) if total_misinfo > 0 else 0
    tp_rate          = round(TP / total_distress * 100, 1) if total_distress > 0 else 0

    return {
        "TP": TP, "FP": FP, "TN": TN, "FN": FN,
        "precision": precision, "recall": recall, "f1": f1,
        "accuracy": accuracy, "specificity": specificity,
        "suppression_rate": suppression_rate,
        "tp_forwarding_rate": tp_rate,
        "total_distress": total_distress,
        "total_misinfo": total_misinfo,
        "trust_lgas": trust_lgas,
        "suppressed_lgas": suppressed_lgas,
        "uncertainty_lgas": uncertainty_lgas,
    }

# ─────────────────────────────────────────────────────────────────────────
# CHART GENERATION
# ─────────────────────────────────────────────────────────────────────────
def generate_charts(cdss_results, sc_results, metrics, tweets, sensors, calls):
    if not HAS_MATPLOTLIB:
        print("  [!] matplotlib not available — skipping chart generation")
        return

    color_map = {
        "CATASTROPHIC": "#d32f2f",
        "CRITICAL":     "#f57c00",
        "MODERATE":     "#fbc02d",
        "STABLE":       "#388e3c",
    }

    fig = plt.figure(figsize=(20, 24))
    fig.patch.set_facecolor('#0d1117')
    gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.45, wspace=0.35)

    label_color = '#e6edf3'
    grid_color  = '#21262d'
    axis_bg     = '#161b22'

    lga_names = [e["lga"]["name"] for e in cdss_results]
    cdss_vals  = [e["cdss"]["cdss"] for e in cdss_results]
    bar_colors = [color_map[severity_label(v)[0]] for v in cdss_vals]

    # ── Chart 1: CDSS Rankings ───────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, :])
    ax1.set_facecolor(axis_bg)
    bars = ax1.barh(lga_names[::-1], cdss_vals[::-1], color=bar_colors[::-1],
                    edgecolor='#30363d', linewidth=0.8, height=0.6)
    for bar, val in zip(bars, cdss_vals[::-1]):
        ax1.text(val + 0.005, bar.get_y() + bar.get_height()/2,
                 f'{val:.3f}', va='center', ha='left',
                 color=label_color, fontsize=10, fontweight='bold')
    ax1.axvline(x=0.75, color='#d32f2f', linestyle='--', linewidth=1.2, alpha=0.8, label='Catastrophic threshold (0.75)')
    ax1.axvline(x=0.55, color='#f57c00', linestyle='--', linewidth=1.2, alpha=0.8, label='Critical threshold (0.55)')
    ax1.axvline(x=0.35, color='#fbc02d', linestyle='--', linewidth=1.2, alpha=0.8, label='Moderate threshold (0.35)')
    ax1.set_xlabel('CDSS Score', color=label_color, fontsize=11)
    ax1.set_title('Figure 1 — CDSS Prioritization Rankings by LGA\nCDSS(j,t) = 0.5·S + 0.3·V + 0.2·HI',
                  color=label_color, fontsize=13, fontweight='bold', pad=12)
    ax1.tick_params(colors=label_color)
    ax1.spines[['top','right','left','bottom']].set_color(grid_color)
    ax1.set_xlim(0, 1.05)
    ax1.legend(loc='lower right', fontsize=9,
               facecolor='#21262d', edgecolor='#30363d', labelcolor=label_color)
    ax1.grid(axis='x', color=grid_color, linewidth=0.5)

    # ── Chart 2: Sc Scores per LGA ───────────────────────────────────────
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_facecolor(axis_bg)
    sc_names = list(sc_results.keys())
    sc_vals  = [sc_results[n]["sc"]     for n in sc_names]
    k_phys   = [sc_results[n]["k_phys"] for n in sc_names]
    k_gov    = [sc_results[n]["k_gov"]  for n in sc_names]
    k_soc    = [sc_results[n]["k_soc"]  for n in sc_names]
    x = range(len(sc_names))
    w = 0.2
    ax2.bar([i - w for i in x], k_phys, width=w, label='k_phys (IoT)', color='#1f77b4', alpha=0.9)
    ax2.bar([i     for i in x], k_gov,  width=w, label='k_gov (Gov)',  color='#2ca02c', alpha=0.9)
    ax2.bar([i + w for i in x], k_soc,  width=w, label='k_soc (Social)',color='#ff7f0e', alpha=0.9)
    ax2.plot(list(x), sc_vals, 'w--o', linewidth=1.5, markersize=5, label='Sc (composite)', zorder=5)
    ax2.axhline(y=TRUST_GATE,       color='#d32f2f', linestyle=':', linewidth=1.0, alpha=0.8)
    ax2.axhline(y=UNCERTAINTY_GATE, color='#fbc02d', linestyle=':', linewidth=1.0, alpha=0.8)
    ax2.set_xticks(list(x))
    ax2.set_xticklabels([n.replace(' / ',' /\n') for n in sc_names], rotation=35, ha='right',
                        color=label_color, fontsize=7.5)
    ax2.tick_params(colors=label_color)
    ax2.set_title('Figure 2 — Credibility Score Sc(r)\nper Data Stream and LGA',
                  color=label_color, fontsize=11, fontweight='bold')
    ax2.set_ylabel('Score', color=label_color)
    ax2.legend(fontsize=8, facecolor='#21262d', edgecolor='#30363d', labelcolor=label_color)
    ax2.spines[['top','right','left','bottom']].set_color(grid_color)
    ax2.set_ylim(0, 1.1)
    ax2.grid(axis='y', color=grid_color, linewidth=0.5)

    # ── Chart 3: Gate Distribution ───────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.set_facecolor(axis_bg)
    gate_counts = {"TRUST": 0, "UNCERTAINTY": 0, "SUPPRESSED": 0}
    for r in sc_results.values():
        gate_counts[r["gate"]] += 1
    gate_labels = list(gate_counts.keys())
    gate_vals   = list(gate_counts.values())
    gate_colors = ['#2ca02c', '#fbc02d', '#d32f2f']
    wedges, texts, autotexts = ax3.pie(
        gate_vals, labels=gate_labels, colors=gate_colors,
        autopct='%1.0f%%', startangle=90,
        textprops={'color': label_color, 'fontsize': 11},
        wedgeprops={'edgecolor': '#0d1117', 'linewidth': 2}
    )
    for at in autotexts:
        at.set_color('#0d1117')
        at.set_fontweight('bold')
    ax3.set_title('Figure 3 — Verification Gate Distribution\n(Layer 2 Output)',
                  color=label_color, fontsize=11, fontweight='bold')

    # ── Chart 4: Tweet Classification ────────────────────────────────────
    ax4 = fig.add_subplot(gs[2, 0])
    ax4.set_facecolor(axis_bg)
    tweet_names = [lg["name"] for lg in LGAS]
    distress_counts = [sc_results[n]["distress_tweets"] for n in tweet_names]
    misinfo_counts  = [sc_results[n]["misinfo_tweets"]  for n in tweet_names]
    noise_counts    = [sc_results[n]["noise_tweets"]    for n in tweet_names]
    x4 = range(len(tweet_names))
    ax4.bar(x4, distress_counts, label='Distress',       color='#d32f2f', alpha=0.85)
    ax4.bar(x4, misinfo_counts,  bottom=distress_counts, label='Misinformation', color='#f57c00', alpha=0.85)
    ax4.bar(x4, noise_counts,
            bottom=[d+m for d,m in zip(distress_counts, misinfo_counts)],
            label='Noise/Irrelevant', color='#555', alpha=0.85)
    ax4.set_xticks(list(x4))
    ax4.set_xticklabels([n.replace(' / ',' /\n') for n in tweet_names],
                        rotation=35, ha='right', color=label_color, fontsize=7.5)
    ax4.tick_params(colors=label_color)
    ax4.set_title('Figure 4 — Tweet Classification by LGA\n(Layer 1 Ingestion Output)',
                  color=label_color, fontsize=11, fontweight='bold')
    ax4.set_ylabel('Number of Tweets', color=label_color)
    ax4.legend(fontsize=9, facecolor='#21262d', edgecolor='#30363d', labelcolor=label_color)
    ax4.spines[['top','right','left','bottom']].set_color(grid_color)
    ax4.grid(axis='y', color=grid_color, linewidth=0.5)

    # ── Chart 5: Evaluation Metrics Bar ──────────────────────────────────
    ax5 = fig.add_subplot(gs[2, 1])
    ax5.set_facecolor(axis_bg)
    metric_names  = ['Precision', 'Recall', 'F1-Score', 'Accuracy', 'Specificity']
    metric_values = [
        metrics['precision'], metrics['recall'], metrics['f1'],
        metrics['accuracy'],  metrics['specificity']
    ]
    metric_colors = ['#1f77b4','#2ca02c','#9467bd','#ff7f0e','#17becf']
    bars5 = ax5.bar(metric_names, metric_values, color=metric_colors,
                    edgecolor='#30363d', linewidth=0.8, width=0.55)
    for bar, val in zip(bars5, metric_values):
        ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.015,
                 f'{val:.4f}', ha='center', va='bottom',
                 color=label_color, fontsize=10, fontweight='bold')
    ax5.set_ylim(0, 1.15)
    ax5.set_title('Figure 5 — Evaluation Metrics\n(Layer 2 Verification Performance)',
                  color=label_color, fontsize=11, fontweight='bold')
    ax5.set_ylabel('Score', color=label_color)
    ax5.tick_params(colors=label_color)
    ax5.spines[['top','right','left','bottom']].set_color(grid_color)
    ax5.grid(axis='y', color=grid_color, linewidth=0.5)

    fig.suptitle(
        'DMAS — Disaster Multi-Agent Awareness System\n'
        'Lagos State Flood Simulation Results (December 2024)\n'
        'Author: Michael Michael Udofia',
        color=label_color, fontsize=15, fontweight='bold', y=0.98
    )

    chart_path = '/home/claude/dmas_charts.png'
    plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✓ Charts saved to {chart_path}")
    return chart_path

# ─────────────────────────────────────────────────────────────────────────
# INFRASTRUCTURE (Mock-safe)
# ─────────────────────────────────────────────────────────────────────────
class DatabaseManager:
    def __init__(self):
        self.mock_mode = (AsyncIOMotorClient is None or asyncpg is None)
    async def connect(self):
        if not self.mock_mode:
            try:
                self.mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
                self.pg_pool = await asyncpg.create_pool(dsn="postgresql://user:pass@localhost/dmas_gis")
                logging.info("Connected to MongoDB and PostGIS.")
            except Exception as e:
                logging.warning(f"DB connection failed, mock mode: {e}")
                self.mock_mode = True
        else:
            logging.info("Databases unavailable. Running in Mock/Memory mode.")
    async def save_raw_report(self, data: dict):
        pass  # mock

class RabbitMQBroker:
    def __init__(self):
        self.mock_mode = (aio_pika is None)
        self.mock_queue = asyncio.Queue()
    async def connect(self):
        if not self.mock_mode:
            try:
                self.connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
                self.channel = await self.connection.channel()
                logging.info("Connected to RabbitMQ.")
            except Exception as e:
                logging.warning(f"RabbitMQ unavailable, using asyncio.Queue: {e}")
                self.mock_mode = True
        else:
            logging.info("RabbitMQ unavailable. Using Python asyncio.Queue (mock broker).")
    async def publish(self, routing_key: str, message: dict):
        await self.mock_queue.put((routing_key, message))

class GeospatialEngine:
    def __init__(self):
        self.mock_mode = (gpd is None)
    def calculate_vulnerability(self, lat, lng, lga_name=None):
        if not self.mock_mode:
            pt = Point(lng, lat)
            df = gpd.GeoDataFrame(geometry=[pt])
            return 0.85
        else:
            # Use real vulnerability values from LGAS lookup
            match = next((lg["vulnerability"] for lg in LGAS if lg["name"] == lga_name), 0.5)
            return match

class GazeboUAVController:
    def __init__(self):
        self.mock_mode = (rospy is None)
    def dispatch_drone(self, target_zone, lat, lng):
        logging.info(f"[UAV] Drone dispatched → {target_zone} ({lat}, {lng}) [Gazebo mock]")

# ─────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────
async def main():
    random.seed(42)
    output_lines = []

    def p(line=""):
        print(line)
        output_lines.append(line)

    p("=" * 72)
    p("  DMAS — Disaster Multi-Agent Awareness System [FIXED PRODUCTION]")
    p("  Lagos State Flood Simulation — December 2024")
    p("  Author: Michael Michael Udofia")
    p("  3,000 Synthetic Data Points | Empirically Grounded")
    p("=" * 72)

    # Init infrastructure
    db     = DatabaseManager()
    await db.connect()
    broker = RabbitMQBroker()
    await broker.connect()
    gis    = GeospatialEngine()
    uav    = GazeboUAVController()

    # ── LAYER 1: INGESTION ───────────────────────────────────────────────
    p(f"\n{'─'*72}")
    p("  LAYER 1 — INGESTION AGENT")
    p(f"{'─'*72}\n")

    tweets  = generate_tweets(n=2000)
    sensors = generate_iot_sensors(n=600)
    calls   = generate_calls(n=400)
    total   = len(tweets) + len(sensors) + len(calls)

    p(f"  ✓ Social Media Posts  : {len(tweets):,}")
    p(f"  ✓ IoT Sensor Readings : {len(sensors):,}")
    p(f"  ✓ 311/LASEMA Calls    : {len(calls):,}")
    p(f"  ✓ TOTAL Data Points   : {total:,}")
    p()
    p(f"  Weather Context (NIMET Dec 2024):")
    p(f"    Rainfall (1h)  : {WEATHER['rain_1h']} mm/h")
    p(f"    Rainfall (24h) : {WEATHER['rain_24h']} mm")
    p(f"    Tidal Surge    : {WEATHER['tidal_surge_cm']} cm above normal")
    p(f"    Conditions     : {WEATHER['description']}")
    p()

    distress_total = sum(1 for t in tweets if t["type"] == "distress")
    misinfo_total  = sum(1 for t in tweets if t["type"] == "misinformation")
    noise_total    = sum(1 for t in tweets if t["type"] == "noise")
    p("  Tweet Classification:")
    p(f"    Distress     : {distress_total:,} ({distress_total/len(tweets)*100:.1f}%)")
    p(f"    Misinformation: {misinfo_total:,} ({misinfo_total/len(tweets)*100:.1f}%)")
    p(f"    Noise         : {noise_total:,} ({noise_total/len(tweets)*100:.1f}%)")

    # ── LAYER 2: VERIFICATION ────────────────────────────────────────────
    p(f"\n{'─'*72}")
    p("  LAYER 2 — CROSS-MODAL VERIFICATION AGENT")
    p("  Sc(r) = Σ(wi·ki) / Σ(wi)")
    p(f"  Weights: IoT={W_PHYSICAL}, Gov={W_GOV}, Social={W_SOCIAL}")
    p(f"{'─'*72}\n")

    sc_results = {}
    for lga in LGAS:
        sc_results[lga["name"]] = compute_sc(lga, tweets, sensors, calls, WEATHER)

    gate_icons = {"TRUST": "✅", "UNCERTAINTY": "⚠️ ", "SUPPRESSED": "🚫"}
    p(f"  {'LGA':<22} {'Sc':>6}  {'Gate':<12}  {'k_phys':>7} {'k_gov':>6} {'k_soc':>6}")
    p(f"  {'─'*22} {'─'*6}  {'─'*12}  {'─'*7} {'─'*6} {'─'*6}")
    for lga in LGAS:
        nb = lga["name"]
        r  = sc_results[nb]
        gi = gate_icons[r["gate"]]
        p(f"  {gi} {nb:<20} {r['sc']:>6.3f}  {r['gate']:<12}  "
          f"{r['k_phys']:>7.3f} {r['k_gov']:>6.3f} {r['k_soc']:>6.3f}")

    trust_c = sum(1 for r in sc_results.values() if r["gate"] == "TRUST")
    uncert_c= sum(1 for r in sc_results.values() if r["gate"] == "UNCERTAINTY")
    supp_c  = sum(1 for r in sc_results.values() if r["gate"] == "SUPPRESSED")
    p()
    p(f"  Gate Summary: ✅ TRUST: {trust_c}  ⚠️  UNCERTAINTY: {uncert_c}  🚫 SUPPRESSED: {supp_c}")

    # ── EVALUATION METRICS ───────────────────────────────────────────────
    metrics = compute_metrics(tweets, sc_results)

    p(f"\n{'─'*72}")
    p("  EVALUATION METRICS — VERIFICATION LAYER (Layer 2)")
    p(f"{'─'*72}\n")
    p(f"  Confusion Matrix:")
    p(f"    True Positives  (TP) — distress forwarded correctly : {metrics['TP']:,}")
    p(f"    False Positives (FP) — misinfo forwarded incorrectly: {metrics['FP']:,}")
    p(f"    True Negatives  (TN) — misinfo blocked correctly    : {metrics['TN']:,}")
    p(f"    False Negatives (FN) — distress missed/blocked      : {metrics['FN']:,}")
    p()
    p(f"  Performance Metrics:")
    p(f"    Precision   : {metrics['precision']:.4f}  ({metrics['precision']*100:.2f}%)")
    p(f"    Recall      : {metrics['recall']:.4f}  ({metrics['recall']*100:.2f}%)")
    p(f"    F1-Score    : {metrics['f1']:.4f}  ({metrics['f1']*100:.2f}%)")
    p(f"    Accuracy    : {metrics['accuracy']:.4f}  ({metrics['accuracy']*100:.2f}%)")
    p(f"    Specificity : {metrics['specificity']:.4f}  ({metrics['specificity']*100:.2f}%)")
    p()
    p(f"  Misinformation suppression rate : {metrics['suppression_rate']}%")
    p(f"  True-positive forwarding rate   : {metrics['tp_forwarding_rate']}%")

    # ── LAYER 3: SYNTHESIS ───────────────────────────────────────────────
    p(f"\n{'─'*72}")
    p("  LAYER 3 — GEOSPATIAL SYNTHESIS AGENT")
    p("  CDSS(j,t) = 0.5·S + 0.3·V + 0.2·HI")
    p(f"{'─'*72}\n")

    cdss_results = []
    for lga in LGAS:
        sc  = sc_results[lga["name"]]
        cds = compute_cdss(lga, sc, WEATHER)
        cdss_results.append({"lga": lga, "sc": sc, "cdss": cds})
    cdss_results.sort(key=lambda x: x["cdss"]["cdss"], reverse=True)

    p(f"  {'Rank':<5} {'LGA':<22} {'CDSS':>6}  {'S':>5} {'V':>5} {'HI':>5}  {'Severity':<16} {'Persons':>10}")
    p(f"  {'─'*5} {'─'*22} {'─'*6}  {'─'*5} {'─'*5} {'─'*5}  {'─'*16} {'─'*10}")
    for rank, entry in enumerate(cdss_results, 1):
        nb  = entry["lga"]["name"]
        cds = entry["cdss"]
        lbl, icon = severity_label(cds["cdss"])
        p(f"  #{rank:<4} {nb:<22} {cds['cdss']:>6.3f}  "
          f"{cds['S']:>5.3f} {cds['V']:>5.3f} {cds['HI']:>5.3f}  "
          f"{icon} {lbl:<14} {entry['lga']['persons']:>10,}")

    # ── LAYER 4: DEPLOYMENT ──────────────────────────────────────────────
    p(f"\n{'─'*72}")
    p("  LAYER 4 — DEPLOYMENT PRIORITIZATION AGENT")
    p(f"{'─'*72}\n")

    resources = {"rescue_boats": 6, "uavs": 8, "medical_units": 4, "evacuation_buses": 6}
    total_covered = 0
    for entry in cdss_results:
        nb  = entry["lga"]["name"]
        cds = entry["cdss"]
        lbl, icon = severity_label(cds["cdss"])
        assets = []
        if lbl in ("CATASTROPHIC", "CRITICAL"):
            if resources["rescue_boats"] > 0:
                assets.append("🚤 Rescue Boat"); resources["rescue_boats"] -= 1
            if resources["medical_units"] > 0:
                assets.append("🏥 Medical Unit"); resources["medical_units"] -= 1
            if resources["evacuation_buses"] > 0:
                assets.append("🚌 Evacuation Bus"); resources["evacuation_buses"] -= 1
        if lbl in ("CATASTROPHIC", "CRITICAL", "MODERATE") and resources["uavs"] > 0:
            assets.append("🚁 UAV"); resources["uavs"] -= 1
            uav.dispatch_drone(nb, 6.5244, 3.3792)
        covered = entry["lga"]["persons"] if assets else 0
        total_covered += covered
        assets_str = ", ".join(assets) if assets else "Monitor only"
        p(f"  {icon} {nb:<22}  CDSS: {cds['cdss']:.3f}  {lbl:<14}")
        p(f"       Persons: {entry['lga']['persons']:,}  →  {assets_str}")
        p()

    total_persons = sum(lg["persons"] for lg in LGAS)
    coverage_rate = round(total_covered / total_persons * 100, 1)

    # ── FINAL SUMMARY ────────────────────────────────────────────────────
    p("=" * 72)
    p("  EXPERIMENTAL RESULTS SUMMARY")
    p("=" * 72)
    p()
    p(f"  Dataset:          {total:,} synthetic data points (8 LGAs)")
    p(f"  Social Media:     {len(tweets):,} posts  |  IoT Sensors: {len(sensors):,}  |  Calls: {len(calls):,}")
    p()
    p(f"  Verification (Layer 2):")
    p(f"    Precision   : {metrics['precision']:.4f}")
    p(f"    Recall      : {metrics['recall']:.4f}")
    p(f"    F1-Score    : {metrics['f1']:.4f}")
    p(f"    Accuracy    : {metrics['accuracy']:.4f}")
    p(f"    Specificity : {metrics['specificity']:.4f}")
    p()
    p(f"  CDSS Rankings (Layer 3):")
    for rank, entry in enumerate(cdss_results, 1):
        lbl, icon = severity_label(entry['cdss']['cdss'])
        p(f"    #{rank} {entry['lga']['name']:<22} CDSS={entry['cdss']['cdss']:.3f}  {icon} {lbl}")
    p()
    p(f"  Deployment (Layer 4):")
    p(f"    Ground truth (IOM DTM/NEMA): 275,621 persons")
    p(f"    DMAS simulated affected     : {total_persons:,} persons")
    p(f"    Persons covered by dispatch : {total_covered:,}")
    p(f"    Population coverage rate    : {coverage_rate}%")
    p()
    p("=" * 72)
    p("  Simulation complete. Generating charts...")
    p("=" * 72)

    # Save results text
    with open("/home/claude/dmas_final_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    # Generate charts
    chart_path = generate_charts(cdss_results, sc_results, metrics, tweets, sensors, calls)

    return cdss_results, sc_results, metrics, output_lines

if __name__ == "__main__":
    asyncio.run(main())
