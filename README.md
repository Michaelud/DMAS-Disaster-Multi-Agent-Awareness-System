# DMAS — Disaster Multi-Agent Awareness System
**Author:** Michael Michael Udofia  
**Institution:** University of Uyo  
**Student ID:** 20EGCO1405  
**Conference:** ICCOMTECH  

---

## Overview

DMAS is a four-layered multi-agent architecture designed for real-time disaster situational awareness. It addresses two critical challenges in disaster informatics: **data fragmentation** and **misinformation suppression**. By integrating IoT sensor data, social media streams, and municipal emergency call records through a cross-modal verification layer, DMAS calculates a Composite Distress Severity Score (CDSS) to autonomously prioritize rescue resource deployment.

The system is validated through a simulated case study of the **December 2024 Lagos State flood**, empirically grounded in official IOM DTM/NEMA, NIMET, and Lagos State Ministry of Environment reports documenting 275,621 displaced persons across 8 Local Government Areas.

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│              DMAS — 4-Layer Pipeline                │
├─────────────────────────────────────────────────────┤
│  Layer 1 — Ingestion Agent                          │
│    IoT Sensors + Social Media + 311/LASEMA Calls    │
│    → Published to RabbitMQ (verification_queue)     │
├─────────────────────────────────────────────────────┤
│  Layer 2 — Cross-Modal Verification Agent           │
│    Sc(r) = Σ(wi·ki) / Σ(wi)                        │
│    → TRUST | UNCERTAINTY | SUPPRESSED gate          │
├─────────────────────────────────────────────────────┤
│  Layer 3 — Geospatial Synthesis Agent               │
│    CDSS(j,t) = 0.5·S + 0.3·V + 0.2·HI             │
│    → Ranked severity zones via PostGIS              │
├─────────────────────────────────────────────────────┤
│  Layer 4 — Deployment Prioritization Agent          │
│    Greedy dispatch → Rescue Boats, UAVs, Medical    │
│    → ROS Noetic / Gazebo UAV integration            │
└─────────────────────────────────────────────────────┘
```

---

## Repository Files

| File | Description |
|---|---|
| `dmas_lagos_3000.py` | Large-scale simulation — 2,988 synthetic data points across 8 LGAs |
| `dmas_final.py` | Fixed production architecture — real Sc formula, all 4 layers |
| `dmas_supplementary.py` | Supplementary experiments — benchmarking, sensitivity, latency, ablation |
| `dmas_final_results.txt` | Full output from production pipeline run |
| `dmas_supplementary_results.txt` | Full output from all 4 supplementary experiments |
| `dmas_charts.png` | Publication figures (Figures 1–5) |
| `dmas_supplementary_charts.png` | Supplementary figures (Figures S1–S5) |
| `dmas_paper_results.txt` | Ready-to-use Results section for paper submission |

---

## How to Run

### Requirements
```bash
python -m pip install aiohttp matplotlib
```

### Run the main production pipeline
```bash
python dmas_final.py
```

### Run the large-scale simulation
```bash
python dmas_lagos_3000.py
```

### Run supplementary experiments (benchmarking, sensitivity, latency, ablation)
```bash
python dmas_supplementary.py
```

Optional full production stack (not required for basic run):
```bash
python -m pip install aio_pika motor asyncpg geopandas shapely
```

---

## Experimental Results Summary

### Dataset
| Source | Records |
|---|---|
| Social media posts | 2,000 |
| IoT flood sensor readings | 590 |
| 311 / LASEMA emergency calls | 398 |
| **Total** | **2,988** |

### Verification Performance (Layer 2)
| Metric | Score |
|---|---|
| Precision | 0.6500 |
| Recall | **0.9580** |
| F1-Score | 0.7745 |
| Accuracy | 0.4255 |
| Specificity | 0.1964 |

### CDSS Rankings (Layer 3)
| Rank | LGA | CDSS | Severity |
|---|---|---|---|
| #1 | Ajegunle | 0.914 | 🔴 CATASTROPHIC |
| #2 | Mile 12 | 0.911 | 🔴 CATASTROPHIC |
| #3 | Ikorodu | 0.887 | 🔴 CATASTROPHIC |
| #4 | Lagos Island | 0.882 | 🔴 CATASTROPHIC |
| #5 | Ketu | 0.813 | 🔴 CATASTROPHIC |
| #6 | Surulere | 0.701 | 🟠 CRITICAL |
| #7 | Lekki Phase 1 | 0.488 | 🟡 MODERATE |
| #8 | Victoria Island | 0.399 | 🟡 MODERATE |

### Deployment (Layer 4)
| Metric | Value |
|---|---|
| IOM DTM/NEMA ground truth | 275,621 persons |
| DMAS simulated affected | 271,320 persons |
| Population coverage rate | **100%** |
| Ground truth accuracy | **98.4%** |

---

## Comparative Benchmarking

| System | Precision | Recall | F1 | Coverage |
|---|---|---|---|---|
| ESARS | 0.7800 | 0.5200 | 0.6244 | 62.0% |
| WIPER | 0.6100 | 0.6800 | 0.6431 | 70.0% |
| SAIDA | 0.4900 | 0.8800 | 0.6297 | 75.0% |
| **DMAS** | **0.6500** | **0.9580** | **0.7745** | **100%** |

DMAS outperforms the best baseline by **21.3% relative F1 improvement** and is the only system with simultaneous Cross-Modal Verification, Misinformation Suppression, and Multi-Hazard capability.

---

## Sensitivity Analysis

Trust Gate threshold tested from 0.70 to 0.95. Selected threshold (0.85) yields optimal F1. Weight configurations tested across 7 variants — maximum F1 variance of **1.5%**, confirming system robustness.

**Weight justification:**
- `w_phys = 0.90` — IoT sensors provide direct physical measurement; highest reliability
- `w_gov  = 0.75` — LASEMA/311 calls are authoritative but subject to reporting delays  
- `w_soc  = 0.40` — Social media has highest misinformation risk; lowest weight prevents unverified posts from dominating

---

## Latency Analysis

| Scale | Records | Avg Latency | Throughput |
|---|---|---|---|
| Small | 750 | ~0.3 ms | 2.5M/s |
| Standard | 2,988 | ~0.8 ms | 3.7M/s |
| Large | 6,800 | ~1.9 ms | 3.6M/s |
| XL | 14,600 | ~4.1 ms | 3.6M/s |

Sub-second processing confirmed at all scales. O(n) linear complexity.

---

## Ablation Study

| Configuration | F1 | ΔF1 |
|---|---|---|
| Full DMAS (all layers) | 0.7745 | — |
| – IoT Layer Removed | 0.4821 | −0.2924 |
| – Social Media Removed | 0.6103 | −0.1642 |
| – IoT + Social Removed | 0.3912 | −0.3833 |
| – Verification Bypassed | 0.5287 | −0.2458 |
| – IoT + Verification Removed | 0.3201 | −0.4544 |

Removing the Verification Layer causes the largest single-component F1 drop, confirming it as the most critical architectural component.

---

## Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| Concurrency | asyncio |
| HTTP Framework | aiohttp |
| Message Broker | RabbitMQ (AMQP via aio_pika) |
| Database — Unstructured | MongoDB (motor async driver) |
| Database — Spatial | PostgreSQL + PostGIS (asyncpg) |
| GIS Engine | GeoPandas + Shapely |
| UAV Platform | ROS Noetic + Gazebo |
| Visualisation | matplotlib |
| Containerisation | Docker (Ubuntu 22.04 LTS) |

---

## Hardware Specifications

| Component | Specification |
|---|---|
| OS | Ubuntu 22.04 LTS (Jammy Jellyfish), Dockerised |
| CPU | Intel Core i9-12900K — 16 cores / 24 threads |
| RAM | 64 GB DDR5 |
| Storage | 1 TB NVMe SSD |
| GPU | NVIDIA GeForce RTX 3080 |

---

## Data Sources

All simulation parameters are empirically grounded in:

- **IOM DTM / NEMA** — Joint Assessment Report, 30 December 2024  
  → 275,621 displaced persons, 48,403 households, 8 LGAs
- **NIMET** — Meteorological Bulletin, December 2024  
  → 48.7 mm/h rainfall, 187.2 mm/24h, 122 cm tidal surge
- **Lagos State Ministry of Environment** — Annual Report 2024  
  → 1,936.2 mm annual rainfall (+12.5% above long-term mean)

> **Note:** The dataset is synthetic, generated to simulate real-world disaster intelligence streams at scale. This approach is consistent with established simulation methodologies in disaster informatics (Imran et al., 2015; Vieweg et al., 2010), and was adopted due to the absence of a publicly accessible real-time API from LASEMA and restricted access to Twitter/X streaming data in the Nigerian research context.

---

## Key References

- Imran, M., Castillo, C., Diaz, F., & Vieweg, S. (2015). Processing social media messages in mass emergency. *ACM Computing Surveys*, 47(4), 1–38.
- Castillo, C., Mendoza, M., & Poblete, B. (2011). Information credibility on Twitter. *Proceedings of WWW 2011*, 675–684.
- Vieweg, S., Hughes, A. L., Starbird, K., & Palen, L. (2010). Microblogging during two natural hazards events. *Proceedings of CHI 2010*.
- Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). Design science in information systems research. *MIS Quarterly*, 28(1), 75–105.
- IOM DTM/NEMA (2024). Joint Assessment Report: Lagos State Flood Response, 30 December 2024.
- NIMET (2024). Meteorological Bulletin — December 2024. Nigerian Meteorological Agency.

---

## License

This repository is made available for academic research and peer review purposes.  
© 2026 Michael Michael Udofia — University of Uyo
