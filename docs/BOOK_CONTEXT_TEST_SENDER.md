# Book Context same-signature Android test sender

Module: `android_llm_spike/book-sender-test`

This APK is a synthetic producer used only to validate the signature-protected
Book -> Companion V2 context bridge. It is not Book and contains no textbook
source.

## Why it lives in the same Gradle build

Debug APKs produced in the same Android build environment use the same debug
signing certificate. That lets the test sender exercise Companion V2's
`signature` permission without weakening the receiver to a normal/dangerous
permission.

Install order for a debug test:

1. install `companion-debug.apk`;
2. install `book-sender-test-debug.apk`;
3. open Companion V2;
4. open Book Context Test Sender;
5. create a test session;
6. send context / next section / clear;
7. return to Companion V2 and send a chat message.

The sender uses ordered broadcasts and reports whether MyGPT returned
`Activity.RESULT_OK`.

## What this proves if it passes on device

- both APKs are signed with the same certificate;
- Android grants the custom signature permission;
- explicit-package context delivery reaches Companion V2;
- sequence/TTL/identity validation accepts valid synthetic messages;
- clear delivery removes the current in-process context.

It still does **not** prove that the real Book APK uses the same signing
certificate or implements the producer contract.


## ADB-driven positive signature test

The test sender also exposes an **acceptance-only** command receiver:

- `dev.mygpt.bookcontexttest.action.AUTOMATED_SEND_CONTEXT_V1`
- `dev.mygpt.bookcontexttest.action.AUTOMATED_CLEAR_CONTEXT_V1`

Example:

```powershell
adb shell am broadcast ^
  -n dev.mygpt.bookcontexttest/.BookContextTestCommandReceiver ^
  -a dev.mygpt.bookcontexttest.action.AUTOMATED_SEND_CONTEXT_V1

adb exec-out run-as dev.mygpt.bookcontexttest ^
  cat files/adb-book-result.txt
```

The command receiver itself is intentionally exported because it contains only
synthetic test data. Crucially, it does **not** bypass the Companion permission:
the nested `BOOK_CONTEXT_V1` broadcast is created and sent by the installed
Book test sender process, so Android still evaluates the sender APK's signing
certificate against Companion V2's `signature` permission.

`adb-book-result.txt` records `accepted=true` only when the Companion receiver
returns `Activity.RESULT_OK`.

This mechanism is test-only and must not be copied into the real Book app.
