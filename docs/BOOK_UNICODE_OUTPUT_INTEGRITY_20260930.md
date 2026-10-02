# Book context Unicode output integrity

Base: coherent Unicode retrieval candidate PR #44,
`44e207b420332fff137554296ebf96f937947658`.
This hardens an existing integration; it is not another upstream adoption.

## Reproduced failure

Valid supplementary-character Book text/title became invalid UTF-16 when the
existing Android composer clipped them at its 2800/180-unit limits. A direct
production-composer probe showed that encoding and decoding the prompt as UTF-8
changed it. Such a cutoff can damage supplementary mathematical/CJK characters
before they reach the model.

The runtime diff is two call-site changes: Book title and body now use the same
reviewed `safePrefixLength` helper as history/memory snippets. The helper may
omit one final code unit rather than split a valid surrogate pair.

All existing ceilings remain UTF-16-unit ceilings. Original context, source
references, Book priority, lower-authority JSON boundaries, full current user
text, truncation flags and decoded text accounting remain intact. The fixed
repro now reports 179 title units and 2799 body units, and UTF-8 round-trip is
lossless. The source context is unchanged.

## Evidence and scope

`BookUnicodeBudgetSmoke` exercises the actual renderer/composer using synthetic
Book snapshots and actual Gson JSON parsing:

- Fixed 180/2800-unit boundaries and exact one-unit omission/accounting
- Empty title, zero/one/two-unit output limits, adjacent valid surrogate pairs,
  and an ordinary one-unit BMP character
- 1288 dynamic-cap projections with escaped punctuation and shifted pair alignment
- Accurate title/body truncation flags and `bookTextChars`
- Full 4000-unit supplementary-character current user preservation
- One real JSON boundary and unchanged source SHA/reference
- Valid UTF-16 and byte-preserving UTF-8 encode/decode

The shared local Java gate passes 21 entrypoints, including all previous Gson,
sklearn and AIRI cases. Local Java 21 source/target checks are not Java 8 API
proof; the existing aggregate hosted workflow supplies Java 8 and Java 17
`--release 8` gates on the exact candidate head.

This prevents splitting valid input pairs. It does not repair or newly validate
malformed UTF-16, introduce Unicode normalization, alter Book freshness/signature
checks, validate live Book IPC or rewrite durable data. Physical Android, model
inference and APK acceptance remain separate.
