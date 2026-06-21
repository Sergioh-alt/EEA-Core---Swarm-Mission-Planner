# EEA Swarm Mission Planner — Roadmap

## Version 0.1 — Current MVP

- [x] Mission Intake with input validation
- [x] Environment Analyzer (weather, terrain assessment)
- [x] Swarm Planner (field partitioning, drone assignment)
- [x] Route Planner (boustrophedon paths)
- [x] Resource Planner (battery, liquid, refills, duration)
- [x] Risk Engine (weather, battery, coverage, operational)
- [x] Decision Engine (GO/NO-GO recommendation)
- [x] Streamlit UI with interactive dashboards
- [x] Documentation system (vision, architecture, ADRs)
- [x] Docker deployment support

## Version 0.2 — Dynamic Task Reassignment

- [ ] Real-time mission replanning when conditions change
- [ ] Drone failure handling — redistribute sectors to remaining drones
- [ ] Feedback loop from Risk Engine to Swarm Planner
- [ ] Mission simulation playback
- [ ] Historical mission storage and comparison

## Version 0.3 — Weather-Aware Planning

- [ ] Weather API integration (OpenWeatherMap / NOAA)
- [ ] Wind direction-aware route optimization
- [ ] Time-window scheduling (best conditions prediction)
- [ ] Microclimate consideration for large fields
- [ ] Precipitation probability assessment

## Version 0.4 — Multi-Agent Optimization

- [ ] Genetic algorithm for optimal swarm configuration
- [ ] Heterogeneous drone fleet support (different specs per drone)
- [ ] Multi-objective optimization (time vs. battery vs. coverage)
- [ ] Agent negotiation protocol (EEA Core consensus model)
- [ ] Learning from past missions (Q-table adaptation)

## Version 1.0 — Hive Logistics Integration

- [ ] Base station management (charging, refilling, maintenance)
- [ ] Multi-field mission coordination
- [ ] Supply chain logistics for liquid/battery inventory
- [ ] Fleet scheduling across multiple days
- [ ] Operator shift management

## Version 2.0 — Real Drone Integration

- [ ] MAVLink / DJI SDK connectivity
- [ ] Real-time telemetry dashboard
- [ ] Autonomous mission execution
- [ ] Sensor fusion (NDVI, thermal, multispectral)
- [ ] Computer vision for crop health assessment
- [ ] Integration with EEA Core's full agent swarm
