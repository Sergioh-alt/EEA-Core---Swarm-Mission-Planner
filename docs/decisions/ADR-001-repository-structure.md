# ADR-001: Repository Structure

**Status**: Accepted
**Date**: 2026-06-21

## Context

The EEA Swarm Mission Planner is the first public module of the EEA Core ecosystem. It must be self-contained yet follow conventions that allow future modules to integrate seamlessly.

The repository must support:
- Clear separation of concerns (core logic vs. UI vs. configuration)
- First-class documentation
- Easy onboarding for new contributors
- Containerized deployment

## Decision

Adopt the following structure:

```
EEA-Swarm-Mission-Planner/
├── app.py              # Streamlit entry point
├── config/             # Configuration and constants
├── core/               # Planning engine modules
├── ui/                 # Streamlit UI components
├── utils/              # Shared utilities (logging, validation)
├── tests/              # Test suite
├── docs/               # Documentation system
│   ├── architecture/
│   ├── decisions/
│   ├── research/
│   ├── changelog/
│   └── roadmap/
├── requirements.txt
├── Dockerfile
└── README.md
```

Key conventions:
- `core/` contains only business logic — no UI imports
- `ui/` depends on `core/` but never the reverse
- `config/` is the single source of truth for all constants
- `docs/` follows a numbered document system

## Consequences

**Positive**:
- Clear dependency direction prevents circular imports
- Core modules can be tested independently of the UI
- Documentation is discoverable and versioned alongside code
- Structure scales to additional modules (sensor fusion, real drone integration)

**Negative**:
- Slightly more files than a single-script approach
- Requires discipline to maintain separation
