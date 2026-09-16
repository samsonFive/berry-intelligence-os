# Publication trust boundaries

## Record boundaries

| Stage | Storage/trust | Permitted next effect |
|---|---|---|
| Discovery | Operational discovery record | Attempt acquisition or transcription. |
| Acquisition/transcription | Private outcome and content artifacts | Create or revise a publication draft with provenance. |
| Publication draft | Private, untrusted, reviewable | Human publication decision only. |
| Trusted publication | Published `publication_artifact` compatibility record | Static metadata/excerpt projection and qualified Atomic proposal generation. |
| Atomic proposal | Private, untrusted `atomic_evidence` proposal | Individual human Atomic-Evidence review. |
| Trusted Atomic Evidence | Human-approved atomic proposition | Fact/relationship workflows allowed by their own contracts. |

## Non-negotiable boundaries

- Acquisition, transcription, extraction, ranking, or model output never grants trust.
- Publication approval is a human gate and creates only a trusted publication.
- Publication approval creates no Fact, Relationship, Entity, Signal, Assessment, or approved Atomic Evidence.
- Existing canonical entity IDs may be linked only after resolution. Suggested names do not authorize entity creation.
- Atomic extraction runs after publication approval and emits private proposals. Each proposal has an independent human gate.
- Queue membership, spreadsheet rows, review sessions, and bulk dismiss do not authorize approval.
- Drafts, full private bodies, reviewer comments, journals, events, and Atomic proposals cannot enter the static build.
- Source Health reports collection and body-acquisition health. Publication-review throughput and current usable coverage remain separate measures.

## Required compatibility change

The current `ReviewPublishService.publish()` can create/update entities and create Facts and Relationships from the publication form. An implementation of this contract must route publication approval through a new boundary-safe command service and remove those side effects from the approval adapter. Existing historical records remain valid; the new service must not rewrite them.

The shared Evidence schema is a storage compatibility layer. Consumers must use `evidence_role`, review state, content quality, and trust projection. Treating every published Evidence-shaped record as an approved factual claim violates this contract.

## Static trust projection

A trusted publication can expose approved metadata, source attribution, bounded excerpt, and outbound link. Full-body redistribution requires a separate legal/product decision. Limited-content publications are labeled and excluded from readable-content, current-company-coverage, and Atomic-extraction success counts.
