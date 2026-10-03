# Book ↔ mygpt StudyBridge — dated source snapshot

This is an isolated archive of the mygpt-side source changes from the local Book progress wiring work. It is not yet an active production connection.

## Verification summary

- Same synthetic Book progress gate/input: baseline **4/13** (exit 1), modified **22/22** (exit 0), rollback **4/13** (exit 1); rollback hash matched baseline.
- The local wiring suite reported **24/24** tests passing.
- The inspected Relay endpoint did not establish an MCP server; GET checks were denied with HTTP 403. No login, credentials, or remote write was performed.
- Actual model provider, dot subscription/callback, and Live chat ingress remain unbound. Real model calls: **0**. Real dot calls: **0**.
- This PR archives files under `deliverables/`; it does not change the default runtime or claim the end-to-end system is live.
- Local user-binding/audit metadata is excluded from this public snapshot. The executable and complete evidence bundle are separate deliverables.