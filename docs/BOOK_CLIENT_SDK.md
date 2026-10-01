# Book client SDK for MyGPT Companion V2

Module: `android_llm_spike/book-client-sdk`

Artifact: `book-client-sdk-release.aar`

This module is the intended producer-side integration surface for the future
real Book Android app. It does not modify the Book repository in PR #15.

## What it provides

- `BookCompanionSession`
  - fixed session/course/book/version identity;
  - independent context and study sequences;
  - study epoch handling;
  - sequence state advances only after Companion V2 returns
    `Activity.RESULT_OK`.
- `BookContextPayload`
  - receiver-compatible identifier/SHA/text/TTL validation.
- `BookCompanionClient`
  - explicit-package ordered broadcasts;
  - send context;
  - clear context;
  - start/end/pause/resume/help/repeated-error/context-changed study signals;
  - revoke study session;
  - delivery callback with accepted/rejected result.
- library manifest automatically requests
  `dev.mygpt.companionv2.permission.BOOK_CONTEXT`.

## Integration sketch

```java
BookCompanionSession session = new BookCompanionSession(
    "study-" + System.currentTimeMillis(),
    "functional-analysis",
    "jiang-ze-jian",
    "book@v1"
);

BookCompanionClient client = new BookCompanionClient(context);

BookContextPayload payload = new BookContextPayload(
    "functional-analysis",
    "jiang-ze-jian",
    "book@v1",
    "ch1-s1",
    "record-001",
    sourceSha256,
    BookCompanionContract.Mode.LEARN,
    "第一节",
    boundedStructuredProjection,
    120_000L
);

client.sendContext(session, payload, result -> {
    if (result.accepted) {
        client.startStudy(session, 120_000L, ignored -> {});
    }
});
```

## Process restart rule

Session sequence state is intentionally in memory. If the Book process is
recreated, create a **new session id** and restart sequence at 1. Do not guess
the previous sequence.

## User agency

The SDK can send explicit Book study facts/events. It cannot enable MyGPT's
supervision opt-in. That control remains local to Companion V2.

## Privacy

The SDK does not:
- persist textbook body text;
- read screens;
- use Accessibility;
- capture audio;
- access the network;
- request overlay permission.

Book decides what bounded structured projection to send. MyGPT continues to
treat it as lower-authority data.


## Synthetic device acceptance uses the SDK

The ADB-driven `BookContextTestCommandReceiver` now calls
`BookCompanionClient` for context, clear and all study events. It no longer
hand-builds those Companion intents.

Therefore the Xiaomi 14 context/supervision acceptance path exercises the same
AAR API intended for the future real Book app. Result files include
`sdk=true`.

The Windows local build also produces and SHA-256 records
`book-client-sdk-release.aar`.


## Preflight

`BookCompanionClient.preflight()` checks the local integration before any
sequence is reserved:

- Companion package installed;
- Android package signatures match according to `PackageManager.checkSignatures`;
- the Book app currently holds
  `dev.mygpt.companionv2.permission.BOOK_CONTEXT`.

Possible statuses:
- `READY`
- `TARGET_NOT_INSTALLED`
- `SIGNATURE_MISMATCH`
- `PERMISSION_NOT_GRANTED`

Every send method runs the same preflight. If it is not READY, the callback
returns `PREFLIGHT_<STATUS>` and **no context/study sequence is consumed**.

The library manifest also declares a package-visibility query for
`dev.mygpt.companionv2`, so Android 11+ package visibility does not turn the
preflight into a false "not installed" result.

This makes real Book adoption failures diagnosable before any ordered broadcast
and also catches install/signature configuration problems without weakening the
signature-protected receiver.
