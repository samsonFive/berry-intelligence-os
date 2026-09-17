# Dependency gate

## Final result: PASS

| Dependency | Stable remote tip | Required artifacts | Report status |
|---|---|---|---|
| Backend | `cf6d19319363dadd20d7182d5b8aaf3f97726d7b` | Present | Local/remote completion reported; no mutation route exposed. |
| Read-only UI | `d19ee0a35033a574dec6c03ecf6aa5008ed7102d` | Present | Read-only, fixture-safe, decisions disconnected. |
| Adversarial validation | `7873a685042f1bd4d16d93137981737854802be4` | Present | `PASS`; exact backend SHA verified. |

The initial four-hour shell poll expired while Luna's remote branch was absent. No integration branch or partial worktree had been created. The user then explicitly resumed the task with “go all else is clear.” A fresh gate check found all three branches. Their tips remained unchanged across two checks more than two minutes apart; all required artifacts were read before integration.

Luna's `CLAUDE-HEAD-VERIFICATION.md` states that `cf6d19319363dadd20d7182d5b8aaf3f97726d7b` was tested, remained stable across three checks, and contained the required backend artifacts. `VERDICT.md` is `PASS`.
