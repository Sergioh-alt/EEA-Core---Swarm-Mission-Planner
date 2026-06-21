# EEA Swarm Mission Planner

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.45-FF4B4B?logo=streamlit)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)
[![Status](https://img.shields.io/badge/Status-MVP%20v0.1-brightgreen)]()
[![EEA Core](https://img.shields.io/badge/EEA%20Core-Module-FF6F00)]()

Decision-support platform that simulates how **EEA Core** would coordinate a swarm of agricultural drones. Analyzes missions, allocates drones, partitions fields, estimates resources, evaluates risks, and generates autonomous planning recommendations.

**Part of the EEA Core ecosystem** — Cognitive Operating System for Autonomous Decision Systems.

## Architecture

```
User Input (Streamlit)
        |
        v
+------------------+     +----------------------+     +-----------------+
|  Mission Intake  | --> | Environment Analyzer | --> | Swarm Planner   |
+------------------+     +----------------------+     +-----------------+
                                                              |
        +-----------------------------------------------------+
        v
+-----------------+     +------------------+     +---------------+
|  Route Planner  | --> | Resource Planner | --> |  Risk Engine  |
+-----------------+     +------------------+     +---------------+
                                                        |
                                                        v
                                                +-----------------+
                                                | Decision Engine |
                                                +-----------------+
                                                        |
                                                        v
                                                  Recommendation
                                                (GO / NO-GO / CAUTION)
```

Each module is a pure function producing typed dataclasses — no shared state, no side effects. See [Architecture v1](docs/architecture/001_architecture_v1.md) for details.

## Features

- **Mission Analysis** — area categorization, operational complexity, weather assessment
- **Swarm Planning** — automatic field partitioning with interactive sector map
- **Route Planning** — boustrophedon flight paths with overlap avoidance
- **Resource Planning** — battery, liquid, refills, and mission duration estimation
- **Risk Engine** — weather, battery, coverage, and operational risk evaluation with radar visualization
- **Recommendation Engine** — GO/NO-GO decision with confidence scoring and optimization suggestions

## Quick Start

### Local

```bash
# Clone
git clone https://github.com/Sergioh-alt/EEA-Swarm-Mission-Planner.git
cd EEA-Swarm-Mission-Planner

# Install dependencies
pip install -r requirements.txt

# (Optional) Configure environment
cp .env.example .env

# Run
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

### Docker

```bash
docker build -t eea-swarm-planner .
docker run -p 8501:8501 eea-swarm-planner
```

## User Inputs

| Parameter | Range | Default |
|---|---|---|
| Field Size | 0.1 - 10,000 ha | 50 ha |
| Crop Type | wheat, corn, rice, soybean, vineyard, cotton, sugarcane, generic | wheat |
| Drone Count | 1 - 20 | 4 |
| Battery Capacity | 1,000 - 50,000 mAh | 5,000 mAh |
| Liquid Capacity | 1 - 100 L | 10 L |
| Temperature | -10 to 50 C | 25 C |
| Wind Speed | 0 - 60 km/h | 10 km/h |

## System Outputs

| Module | Output |
|---|---|
| **Mission Analysis** | Area category, complexity, weather assessment, flight conditions |
| **Swarm Planning** | Sector map, grid layout, drone assignments, workload balance |
| **Route Planning** | Boustrophedon paths, distances, times, overlap percentages |
| **Resource Planning** | Battery %, liquid L, refill cycles, mission duration, bottleneck |
| **Risk Engine** | Weather/battery/coverage/operational risk scores + mitigations |
| **Recommendation** | GO / GO WITH CAUTION / NO-GO with confidence % and notes |

## Crop Profiles

| Crop | Spray Rate (L/ha) | Altitude (m) | Complexity |
|---|---|---|---|
| Wheat | 8 | 3 | Low |
| Corn | 12 | 5 | Medium |
| Rice | 15 | 3 | High |
| Soybean | 10 | 3 | Low |
| Vineyard | 14 | 4 | High |
| Cotton | 10 | 4 | Medium |
| Sugarcane | 12 | 6 | High |

## Documentation

| Document | Path |
|---|---|
| Project Vision | [docs/000_project_vision.md](docs/000_project_vision.md) |
| Architecture v1 | [docs/architecture/001_architecture_v1.md](docs/architecture/001_architecture_v1.md) |
| ADR-001 Repository Structure | [docs/decisions/ADR-001-repository-structure.md](docs/decisions/ADR-001-repository-structure.md) |
| ADR-002 Streamlit Choice | [docs/decisions/ADR-002-streamlit-choice.md](docs/decisions/ADR-002-streamlit-choice.md) |
| ADR-003 Modular Architecture | [docs/decisions/ADR-003-modular-architecture.md](docs/decisions/ADR-003-modular-architecture.md) |
| Roadmap | [docs/roadmap/roadmap.md](docs/roadmap/roadmap.md) |
| Changelog | [docs/changelog/](docs/changelog/) |

## Future Vision

This project is a planning layer for future systems including:

- **Autonomous drone swarms** — real fleet coordination
- **Hive logistics stations** — base station management
- **Agricultural intelligence** — sensor fusion and crop analysis
- **Multi-agent autonomous coordination** — the universal planning layer
- **Sensor fusion systems** — NDVI, thermal, multispectral integration

See the [Roadmap](docs/roadmap/roadmap.md) for the full evolution plan.

## EEA Core Ecosystem

> Models are replaceable. Knowledge is persistent. Architecture remains.

EEA Core is a modular cognitive infrastructure designed to power autonomous decision-making systems across multiple domains. The Swarm Mission Planner is the first public module demonstrating the Observe → Analyze → Plan → Decide → Recommend cycle.

## License

MIT
