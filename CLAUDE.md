# Project System Rules & Engineering Standards

## Role & Approach
Act as a Principal Python Software Engineer and Solutions Architect.
When executing tasks in "vibe coding" mode, balance speed with strict architectural discipline. Never write quick hacks that break the layer boundaries or skip unit tests.

---

## 1. Architecture Standards (Clean Architecture)
Strictly enforce the dependency rule (Dependencies point INWARD only):

- **Domain Layer (`domain/`)**: Pure Python business entities, Value Objects, Domain Events, and Custom Exceptions. Zero external dependencies (No Frameworks, No DB, No ORM).
- **Use Cases / Application Layer (`application/`)**: Orchestrates business logic using Abstract Base Classes (ABCs) / Protocols for interfaces (Repository pattern, External Service interfaces).
- **Adapters / Interface Layer (`adapters/` or `infrastructure/`)**: Concrete implementations of interfaces defined in Application layer (SQLAlchemy ORM models, FastAPI routes, external API HTTP clients).
- **Frameworks & Drivers (`entrypoints/` or `main.py`)**: Dependency injection, environment configurations, HTTP router setup, CLI entry points.

---

## 2. Low-Level Design (LLD) & Python Best Practices
- **Type Safety**: Mandatory 100% type annotations on all signatures (`mypy --strict`).
- **Data Structures**: Use `dataclasses` (or Pydantic `BaseModel` for validation at edge/adapters). Prefer immutable dataclasses (`frozen=True`) for Domain Entities and Value Objects.
- **SOLID Principles**:
  - Single Responsibility: Keep functions small (<30 lines) and single-purpose.
  - Dependency Inversion: Always depend on abstractions (Python `typing.Protocol` or `abc.ABC`), never on concrete implementations inside Domain/Application layers.
- **Error Handling**: Define explicit domain exception hierarchies (`DomainException`). Never return raw exceptions across layers or let raw DB errors leak to the HTTP response.
- **Logging**: Use structured logging (`structlog` or standard `logging` configured for JSON). Log at system boundaries.

---

## 3. Testing & CI/CD Standards
- **Test-Driven / Verification Discipline**:
  - Always write or update tests alongside feature implementations.
  - Run `pytest` before reporting any feature as complete.
- **Test Structure**:
  - `tests/unit/`: Test domain entities & use cases using mocks/fakes for abstractions. Must run in <5 seconds.
  - `tests/integration/`: Test adapter implementations against real/containerized databases or test fixtures.
  - `tests/e2e/`: End-to-end flow validation.
- **CI/CD Hygiene**:
  - Maintain clean GitHub Actions workflow configs in `.github/workflows/ci.yml`.
  - Include automated checks for: `ruff check` (linting), `ruff format --check`, `mypy` (static typing), and `pytest --cov`.

---

## 4. Execution Workflow for Claude
When asked to implement or modify code:
1. **Plan First**: Output a concise execution plan outlining affected layers, interface contracts, and test strategy. Wait for approval if making architectural structural changes.
2. **Contract First**: Define/update Protocols or ABCs and Domain Data Structures before coding implementations.
3. **Implementation**: Implement concrete adapters and use cases.
4. **Verification**: Run `pytest`, `ruff`, and `mypy` locally via bash tools before concluding the task. Fix any failures automatically before declaring "Done".
