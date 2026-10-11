# D5: Hosting — Azure Container Apps for all milestones

**Status:** Accepted, partly superseded by [D16](016-milestone-alignment.md) (platform built incrementally per milestone) · **Date:** 2026-10-10

## Context
APIM as an API gateway needs a backend it can reach ([D4](004-gateways.md)). We also want one consistent environment from M1 to M8.

## Options
**A. Azure Container Apps** behind APIM
- Pros: true end-to-end cloud architecture; one public URL; strongest portfolio story (APIM, Container Apps, Foundry, managed identity).
- Cons: container images, registry and deployment scripts; small but non-zero cost; harder to debug than local.

**B. APIM self-hosted gateway locally**
- Pros: services stay local.
- Cons: needs Developer (no SLA) or Premium (expensive) tier; less common setup.

**C. Split**: APIM in the cloud as AI gateway only; open-source API gateway locally
- Pros: cheapest; fastest.
- Cons: two gateway products; API gateway not Azure-native.

## Decision
**Option A**, used as the **same target environment for every milestone**. Features are added strictly in milestone order (M1 → M8).

## Consequences
- M1 includes provisioning the base environment (APIM, Container Apps environment, Entra ID, Foundry), so it is the heaviest milestone.
- Containers have no permanent disk, which drives the data-store decision ([D6](006-data-stores.md)).
- Infrastructure defined as code (tool to be decided in the LLD).
