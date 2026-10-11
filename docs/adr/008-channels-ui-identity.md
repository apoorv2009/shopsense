# D8: Channels, UI, identity and email trust

**Status:** Accepted · **Date:** 2026-10-11

## Context
Tickets arrive through chat, email, reviewer actions and batch evaluation. All channels reach the ShopSense API through the API gateway; the ShopSense API always creates the ticket. Customers type free text (the brief tests messy tickets). Email has no login, and the sender address can be forged.

## D8a: User interface
| Option | Pros | Cons |
|---|---|---|
| No UI (Swagger) | No UI work | Weak demo; approval step invisible |
| Python UI (Streamlit/Chainlit) | Fast; same language | Prototype look; poor for two personas with login |
| **Angular SPA on Static Web Apps** | Developer strength; two personas with real authorization; visible human-approval step | Third codebase; needs login design |

**Decision:** Angular SPA with a **customer portal** (my orders, chat, ticket status) and a **reviewer console** (approval queue, case summary, cited policy, proposed action, risk reasons, agent timeline, approve/reject).

## D8b: Email intake
| Option | Pros | Cons |
|---|---|---|
| Simulated email payload | Simple | Email channel only pretended |
| **Logic App on a real mailbox** | Real channel; low-code; email handling outside our API | Mailbox and connector setup |

**Decision:** Logic App trigger on a support mailbox calls APIM `/email`. Email threads continue a ticket via a `[TKT-nnnn]` subject reference.

## D8c: Login
| Option | Pros | Cons |
|---|---|---|
| Entra External ID | Production-realistic | Fiddly setup |
| **Entra ID test users** | Real token validation at APIM; simpler | Customers in a workforce directory is less realistic |
| Mock token issuer | Easiest | Not production-grade |

**Decision:** Entra ID test users with app roles `customer`, `reviewer` and `admin` (added by [LLD-8](../lld/08-angular-app.md)), and a `customer_id` attribute. External ID documented as the production choice.

## D8d: Email trust model
| Option | Pros | Cons |
|---|---|---|
| Trust the sender address | Simple | Spoofed email could trigger refunds |
| **Lower-trust email channel** | Closes spoofing; realistic | Slower email refunds |
| Magic-link verification per ticket | Strong | Friction on every email |

**Decision:**
- Only senders who are **registered Entra users** and whose email **passes DMARC** may create email tickets. Unregistered or unverified senders get an auto-reply; no AI processing; attempt logged.
- Verification is authoritative in the ShopSense API (via Microsoft Graph, using its managed identity), with an early filter in the Logic App.
- **Any refund requested by email always goes to human approval**, whatever the amount.

## D8e: Outbound email
| Option | Pros | Cons |
|---|---|---|
| Same Logic App replies | Replies from real address; threading | No path for replies after an approval pause |
| Azure Communication Services Email | API controls every reply | Different sender domain; weaker threading |
| **Hybrid** | All replies from the same address and thread; queue decouples email outages | Two Logic Apps and a queue |

**Decision:** Hybrid. The Logic App sends immediate replies. Replies after approval go onto an **Azure Storage queue**; a second Logic App sends them from the same mailbox.

## Consequences
- Managed identities used for Logic App → APIM and ShopSense API → Microsoft Graph.
- Whether the mailbox connector exposes `Authentication-Results` headers is verified in the LLD; fallback is fetching headers through Microsoft Graph.
- `channel = email` is an input to the risk gate.
