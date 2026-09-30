# Book SDK preflight acceptance evidence

The synthetic Xiaomi 14 sender now records the client SDK preflight status for
every protected context/clear/study delivery.

A positive device gate requires all four markers:
- `sdk=true`
- `preflight=READY`
- `status=ACCEPTED`
- `accepted=true`

This proves that:
1. the sender used the reusable Book client SDK;
2. Companion was locally visible/installed;
3. Android package signatures matched;
4. the signature permission was actually granted;
5. the protected receiver returned RESULT_OK.

A preflight failure occurs before sequence reservation and therefore cannot burn
the receiver's next expected sequence.
