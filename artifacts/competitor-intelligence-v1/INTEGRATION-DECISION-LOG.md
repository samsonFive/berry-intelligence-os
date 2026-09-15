# Competitor Intelligence integration decision log

Date: 2026-09-15

## Inputs preserved

The dedicated branch was created at base
`bd96fca1231dc97ae4ec3fc316743b0a3f2e8427`. The exact commits were
cherry-picked in the requested order:

1. Claude `4e54401da040be937cc68877f410b4da7b646d65`
2. Sol code `3fcfba8d6feb4218b2a5e9f6f0608dc6fe66b9d7`
3. Sol artifacts `792e729df5d9a440df798b4fe55ac5e363963412`
4. Grok `d44e3e3d753e4f796151e75c6747214b92c8232e`

Git created new cherry-pick SHAs because their parents changed. No textual
conflicts occurred.

## Semantic reconciliation

- Claude's reconciliation matrix is the production roster and identity source.
- Grok's 33-row fixture remains test-only. Production requires canonical rows.
- Sol's runtime discovery state and acquisition ledger supply distinct
  discovery/readability facts. Usable current coverage is computed through the
  existing reader-content honesty gate.
- Spreadsheet labels remain visible while names, aliases, entity types, and
  routes resolve from canonical entities.
- Brand and breeding-program roster members keep their actual entity types.
- Entity `status: unverified` appears as pending identity review without
  removing the represented canonical row.
- Genetics relationship `status: disputed` appears as Pending review.
- California Giant's known official-source block is retained as a diagnosed
  constraint. No acquisition outcome is fabricated in this worktree.

## Runtime boundary

The ignored canary runtime was not copied or reconstructed. This integration
worktree has no `inbox/` directory. The historical Sol audit remains labeled as
an earlier 11/33 base snapshot. The current post-integration audit is stored in
`competitor-source-coverage-current.json` and `.md`.

