# D2: Quality bar — portfolio-grade

**Status:** Accepted · **Date:** 2026-10-10

## Context
The project is graded per milestone, and will also be presented in senior architecture interviews. Course-grade (one deployable, minimal infrastructure) and portfolio-grade (real boundaries, cloud deployment, documented decisions) lead to different designs.

## Options
- **Course-grade:** fastest; a clean demo; but weak architecture story.
- **Portfolio-grade:** every required concept implemented properly, with documented decisions; more effort.

## Decision
**Portfolio-grade.** Implement every concept the brief requires, properly, and record each decision as an ADR. Build features strictly in milestone order (M1 → M8) on the target infrastructure.

## Consequences
- Design is finalised (HLD, LLD, approach) before any code is written.
- Timeline pressure is accepted in exchange for correctness.
