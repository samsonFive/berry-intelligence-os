# Authorization

## The gap this closes

The existing `/review/{id}/publish` route requires only a nonblank
`reviewer` form field (`app/main.py`) — free text, not an authenticated
identity. Luna's safety audit (`audit/publication-review-safety-v1`,
`MISSING-ENFORCEMENT.md`) named this explicitly: "actor authorization that
distinguishes a human reviewer from AI, bot, or service identities" was
missing enforcement.

## Design

`ActorIdentity` (`app/services/publication_review_command.py`) is a
structured, frozen dataclass — never constructed from raw form text:

```python
@dataclass(frozen=True)
class ActorIdentity:
    actor_id: str
    kind: str  # "human" | "ai" | "bot" | "service"
    permissions: frozenset[str]
    authenticated: bool = True
```

The command envelope carries only `actor_id` (a string). The service
resolves it through an injected `ActorDirectory` port:

```python
class ActorDirectory(Protocol):
    def resolve(self, actor_id: str) -> ActorIdentity | None: ...
```

`is_authorized_human_reviewer(actor)` requires all three:
`actor is not None`, `actor.authenticated`, `actor.kind == "human"`, and
`"publication_review" in actor.permissions`. Every decision command calls
`_authorize()` first, before any draft is even loaded — an unauthorized
caller learns nothing about draft state.

No session/cookie/JWT parsing lives in this module. A real deployment's
HTTP layer resolves its own authenticated session to an `ActorIdentity`
and implements `ActorDirectory` (or wraps whatever identity provider it
already has behind it) — this mission does not build that adapter, since
no route is wired to this service (`NON-GOALS`: "No production mutation
route exposed to users"). `InMemoryActorDirectory` exists only for tests
and any future adapter's own tests.

## What is rejected, and how it is proven

| Caller | `kind` | Result |
|---|---|---|
| No such actor id | — | `unauthenticated` |
| Session expired (`authenticated=False`) | `human` | `unauthenticated` |
| Human with no `publication_review` permission | `human` | `forbidden` |
| AI | `ai` | `forbidden` |
| Bot/scheduled job | `bot`/`service` | `forbidden` |
| Authorized human | `human` | Succeeds |

`tests/test_publication_review_command.py::test_every_automated_actor_kind_produces_byte_identical_state_trees`
snapshots the durable draft file, the entire `data/` tree, and the entire
`inbox/` tree, attempts approval from five different unauthorized/
automated identities, and asserts the snapshot is byte-identical
afterward — not just "the call returned an error," but "nothing was
written at all."

## Reason/comment requirements

Per `APPROVED V1 POLICY`'s "Rejection and correction-required decisions
require a reason": `reject_publication` and
`request_publication_correction` both raise `invalid_command` if `comment`
is blank (`test_reject_requires_a_reason`). `defer_publication` accepts an
optional `review_after` but still requires a typed `reason_code` from a
closed set.

## No bulk approval

Every command targets exactly one `draft_id`. There is no collection
endpoint, no "approve all selected," and no batch parameter anywhere in
`PublicationReviewCommandService`'s signature. A caller wanting to approve
ten items must issue ten separately authorized, separately versioned
commands — exactly `COMMAND-CONTRACTS.md`'s own "V1 defines no collection
endpoint that accepts multiple approval decisions."
