# EEA Swarm Mission Planner

An AI-powered swarm intelligence system for autonomous agricultural drone mission planning.

---

## Overview

EEA Swarm Mission Planner is a modular simulation and planning system designed to model, optimize, and execute autonomous multi-drone agricultural missions.

It evolves from simple grid-based simulation into a full geometric, intelligent, and swarm-based decision system.

The system is built incrementally using strict engineering phases, ensuring correctness, reproducibility, and scalability.

---

## Architecture

The system is structured into five progressive layers:

### v0.1 — Simulation Core
- Grid-based field partitioning
- Basic swarm planning
- Risk evaluation pipeline
- Streamlit UI (initial version)

### v0.2 — GIS Foundation
- Real polygon-based fields (Shapely)
- Area-aware geometry system
- Validated field construction
- Geometry-safe mission intake

### v0.3 — Operational Simulation
- Time-based mission execution
- Drone operational modeling
- Battery and resource simulation
- Realistic mission timeline engine

### v0.4 — UI + Visualization
- Polygon drawing interface
- Live mission visualization
- Sector rendering (grid + strip modes)
- Interactive mission configuration

### v0.5 — System Stabilization (CURRENT)
- Full architecture consolidation
- End-to-end pipeline validation
- Refactoring and cleanup
- Regression testing across all modules

---

## Core Principles

- Physical reality first, intelligence second
- Strict phase-based development
- No feature skipping
- Full validation before progression
- AI-assisted co-development (Devin integration)

---

## Testing Philosophy

Every phase must pass:

- Regression tests (v0.1 compatibility)
- Geometry validation
- Mission execution consistency
- Multi-scenario stability tests

No phase is accepted without full system verification.

---

## Project Structure

```
core/           # Decision pipeline modules (7 stateless pure-function modules)
ui/             # Streamlit interface components
utils/          # Validators, logger, shared utilities
config/         # Settings, crop profiles, constants
docs/           # Architecture, decisions, roadmap, changelog
tests/          # Regression and validation tests
```

---

## Quick Start

```bash
# Clone
git clone https://github.com/Sergioh-alt/EEA-Core---Swarm-Mission-Planner.git
cd EEA-Core---Swarm-Mission-Planner

# Install dependencies
pip install -r requirements.txt

# Run
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

### Docker

```bash
docker build -t eea-swarm-planner .
docker run -p 8501:8501 eea-swarm-planner
```

---

## Current State

System is in **Phase 5: Stabilization & Consolidation**

All prior phases (v0.1 → v0.4) are implemented but require unification into a single coherent production-grade architecture.

---

## AI Collaboration

This project is co-developed with AI-assisted engineering (Devin) under strict phase control, validation gates, and incremental development rules.

---

## Next Step

System stabilization and full architecture consolidation before production-level scaling.

---

## License

MIT
