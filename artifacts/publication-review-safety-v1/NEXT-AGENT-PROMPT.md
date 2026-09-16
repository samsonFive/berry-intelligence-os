# Next-agent prompt

Before changing publication/review behavior, read `INVARIANT-MATRIX.md` and
`MISSING-ENFORCEMENT.md`. Add an implementation and its fault-injection tests
together. Run the focused command in `VALIDATION-RESULTS.md`, record exact
counts/durations, then run the existing Wave 2 gate. Any change under
`data/` or the operator `inbox/` is a failed validation unless explicitly
authorized as a production migration. Never use AI output as reviewer identity
or bypass the separate publication-to-claim trust decision.
