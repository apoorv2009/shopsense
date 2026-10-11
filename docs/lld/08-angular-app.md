# LLD-8: Angular app

**Status:** Accepted · **Date:** 2026-10-11 · **Milestones:** M5 (reviewer console), M6 (customer chat), M7 (fault switch), M8 (demo)

## Table of contents
- [Decisions](#decisions)
- [Structure](#structure)
- [Pages](#pages)
- [Authentication](#authentication)
- [Chat streaming](#chat-streaming)
- [API additions](#api-additions)
- [Standards](#standards)

## Decisions
| # | Decision |
|---|---|
| L8a | **Latest stable Angular**: standalone components, signals, built-in control flow, zoneless change detection, OnPush, strict TypeScript |
| L8b | **One app**, lazily loaded `/customer`, `/reviewer`, `/admin` areas with role guards (UX only; the API is the security boundary) |
| L8c | **MSAL Angular**, authorization code + PKCE against Entra ID; interceptor attaches the API access token; app roles drive guards |
| L8d | **Angular Material 3** |
| L8e | **Signal-based services** with Angular HTTP resources; no NgRx |
| L8f | **Fetch-based SSE** (`@microsoft/fetch-event-source`) wrapped in a service exposing signals |
| L8g | Pages as listed below; new ShopSense endpoint `GET /v1/me/orders`; evidence photos via short-lived signed links |
| L8h | **Admin fault-switch page** with new Entra role `admin` |
| L8i | **Reviewer queue polled every 10 s** |
| L8j | **Frontend standards** in [`frontend/CLAUDE.md`](../../frontend/CLAUDE.md) |

## Structure
```
frontend/
  src/app/
    core/        # auth (MSAL), API client, interceptors, runtime config, error handling
    shared/      # UI components, pipes (Money formatting from paise)
    customer/    # orders, chat, tickets (lazy)
    reviewer/    # queue, case view, decision (lazy)
    admin/       # fault switch (lazy)
  public/config.json   # runtime configuration
  staticwebapp.config.json
```

## Pages
| Area | Page | Contents |
|---|---|---|
| Customer | My orders | Orders with "Get help with this order" |
| | Chat | Conversation, live progress steps, photo upload, ticket status |
| | My tickets | Tickets with status |
| Reviewer | Approval queue | Pending cases; filter by approver tier and age |
| | Case view | Trusted panel (code risk reasons, code-computed proposed action); "AI-generated" summary panel; "customer's own words" panel; policy citations; evidence photos; agent-step timeline |
| | Decision | Approve / reject with comment |
| Admin | Fault switch | Order Platform latency, error rate, scope, duration |

## Authentication
| Role | Access |
|---|---|
| `customer` | `/customer/*`; chat, tickets, own orders |
| `reviewer` | `/reviewer/*`; approvals |
| `admin` | `/admin/*`; fault switch |

Tokens are validated by APIM and the API; route guards only shape navigation.

## Chat streaming
`EventSource` cannot send an `Authorization` header, so the chat service uses `fetch` with a readable stream (`@microsoft/fetch-event-source`). Event types: `progress` (step label), `reply` (final message), `status` (ticket status change), `error`.

## API additions
Added to the ShopSense API ([LLD-2](02-shopsense-api-structure.md#api-endpoints)):

| Endpoint | Role | Purpose |
|---|---|---|
| `GET /v1/me/orders` | customer | Orders via MCP read tools (browser never reaches the Order Platform) |
| `GET /v1/approvals/{ticket_id}/evidence/{attachment_id}` | reviewer | Short-lived signed link to a photo |
| `GET /v1/admin/faults`, `PUT /v1/admin/faults` | admin | Proxy to the Order Platform fault endpoint |

## Standards
See [`frontend/CLAUDE.md`](../../frontend/CLAUDE.md): strict TypeScript, ESLint, Prettier, feature folders, single API client layer, Vitest, Playwright end-to-end per critical flow, WCAG 2.1 AA, CI (lint, test, build), CSP headers, runtime config.
