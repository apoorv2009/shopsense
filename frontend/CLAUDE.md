# ShopSense Frontend - Angular Standards

Applies to everything under `frontend/`. The root `CLAUDE.md` process rules (design first, source of truth in `docs/`) also apply. Design reference: [`docs/lld/08-angular-app.md`](../docs/lld/08-angular-app.md).

## 1. Angular baseline
- Latest stable Angular; standalone components only (no NgModules).
- Signals for state; built-in control flow (`@if`, `@for`, `@switch`); zoneless change detection; `ChangeDetectionStrategy.OnPush` on every component.
- Strict TypeScript (`strict: true`, `noImplicitOverride`, `noUncheckedIndexedAccess`); no `any`.

## 2. Structure
- Feature folders: `core/`, `shared/`, `customer/`, `reviewer/`, `admin/`; feature areas lazily loaded.
- Components never call `HttpClient` directly; all HTTP goes through the API client layer in `core/`.
- State lives in signal-based services; no global store.
- Money arrives from the API in paise and is formatted only by the shared money pipe; never do arithmetic on display values.

## 3. Security
- Authentication with MSAL Angular (auth code + PKCE); tokens attached by interceptor only.
- Route guards are UX only; never assume a hidden button is a security control.
- Never render customer-supplied text as HTML; no `bypassSecurityTrust*`.
- Content Security Policy and security headers in `staticwebapp.config.json`.
- Runtime configuration from `public/config.json`; no secrets in the bundle.

## 4. UI
- Angular Material 3; WCAG 2.1 AA (keyboard navigation, labels, contrast).
- Reviewer case view keeps trusted (code-generated) information visually separate from AI-generated and customer-supplied text.

## 5. Testing & CI
- Unit tests with Vitest for services, pipes and components.
- End-to-end tests with Playwright, one per critical flow: chat → auto-resolution; chat → approval → resolution; reviewer reject.
- CI: `eslint`, Prettier check, Vitest, production build. Run them before reporting work as done.
