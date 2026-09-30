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
