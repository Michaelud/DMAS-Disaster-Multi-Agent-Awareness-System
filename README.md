# DMAS — Disaster Multi-Agent Awareness System
**Author:** Michael Michael Udofia

## Overview
A multi-agent system for real-time disaster awareness, applied to the
Lagos State flood event of December 2024.

## Files
- `dmas_final.py` — Fixed production architecture (4-layer pipeline)
- `dmas_lagos_3000.py` — Large-scale simulation (2,988 data points)
- `dmas_charts.png` — Publication figures (Figures 1–5)
- `dmas_final_results.txt` — Full simulation results

## How to Run
pip install aiohttp matplotlib
python dmas_final.py

## Data Sources
- IOM DTM/NEMA Joint Assessment Report, 30 Dec 2024
- NIMET Meteorological Bulletin, December 2024
- Lagos State Ministry of Environment, 2024

## Stack
- Language: Python 3.10+
- Broker: RabbitMQ (AMQP)
- Database: MongoDB + PostgreSQL/PostGIS
- GIS: GeoPandas + Shapely
- UAV Platform: ROS Noetic + Gazebo
