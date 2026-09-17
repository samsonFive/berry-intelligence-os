# Frontend integration contract for Grok

No visual controls or production routes are added in V1. A future authenticated route should translate a simple UI action into `FeedbackRequest` and return `FeedbackResult` without duplicating domain rules.

## Request

The server supplies the authenticated actor identity and permissions. The client supplies:

```json
{
  "action": "promote|exclude|defer|undo",
  "object_id": "canonical record id",
  "object_type": "evidence|publication_draft|discovered_media|signal|assessment",
  "intent": "relevant|retain_for_review|monitor|governed_promotion",
  "reason": "optional controlled value",
  "idempotency_key": "unique click/request key",
  "expected_version": 0,
  "source_surface": "today|reader|company|report|research_packet",
  "original_event_id": "required only for undo"
}
```

Never accept an actor ID or permission claim from an untrusted form field. Build `FeedbackActor` from the existing authenticated session/operator context.

## Response behavior

Render `state`, `version`, `blockers`, `event.id`, and the returned `projection`. A thumbs-up using `relevant`, `retain_for_review`, or `monitor` is an endorsement only. Use `governed_promotion` only from a clear Promote action and provide the existing publication-review adapter. Display `pending_promotion` and its blockers instead of implying approval.

Thumbs-down should update the active card projection immediately and offer Undo using the returned event ID and next version. It must not remove the underlying Reader/source link. On a stale-version error, reload the projection. On an idempotency conflict, do not guess which action won.

## Consumer seam

Before including a record in Today, reports, company coverage, or a Research Packet, request the actor-specific projection and honor `eligible_for_trusted_feed`, `excluded_from_trusted_feed`, and `current_news_eligible`. Static/public builds must omit this private state entirely.

Feedback cannot confirm a Signal, create a Fact or Assessment, create a Watch, or promote a Research Packet. Those actions keep their existing governed workflows.
