# Companion V2 Windows + Xiaomi 14 local acceptance

Date: 2026-09-30

This route exists because GitHub hosted Actions currently fail before runner
allocation. It does not replace CI. It provides an exact-branch local build and
device-validation path.

## Prerequisites

- Windows 10 or 11
- JDK 17
- Android SDK with Command-line Tools and platform-tools
- Git
- Xiaomi 14 with USB debugging authorized
- checkout of branch feat/airi-chat-memory-brain-20260929

android_llm_spike now contains a Gradle 8.14.3 wrapper. A global Gradle install
is not required.

## Build and install

From repository root:

~~~powershell
powershell -ExecutionPolicy Bypass -File .\android_llm_spike\scripts\build_and_install_companion_v2.ps1
~~~

Useful switches:

~~~powershell
.\android_llm_spike\scripts\build_and_install_companion_v2.ps1 -SkipInstall
.\android_llm_spike\scripts\build_and_install_companion_v2.ps1 -DeviceSerial <serial>
.\android_llm_spike\scripts\build_and_install_companion_v2.ps1 -SkipSubmoduleUpdate -SkipSdkInstall
~~~

The script:
1. initializes and verifies pinned llama.cpp and sherpa-onnx submodules;
2. installs NDK 29.0.13113456 and CMake 3.31.6 when needed;
3. builds llama JNI, MyGPT bridge, local-LLM APK, Companion V2 and Book sender;
4. verifies Companion V2 and Book sender have the same signing certificate;
5. installs Companion V2 before the sender;
6. records APK hashes, signer digests, package dumps, initial meminfo, thermal and logcat;
7. sends a shell-origin Book broadcast as a negative permission probe.

Evidence is stored under android_llm_spike/device_evidence/<timestamp> and is
gitignored.

## Required external inputs

### Skin

Use the decrypted 3714430278.zip selected for the Live/MyGPT character.

### ASR

Use the official sherpa package:

sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2

Expected core files:
- encoder-epoch-99-avg-1.int8.onnx
- decoder-epoch-99-avg-1.onnx
- joiner-epoch-99-avg-1.int8.onnx
- tokens.txt

### TTS

Optional package:

vits-melo-tts-zh_en.tar.bz2

Expected core files:
- model.onnx
- tokens.txt
- lexicon.txt
- date.fst
- phone.fst
- number.fst

### LLM

Import a compatible GGUF. No default GGUF is accepted yet. Xiaomi 14 speed,
memory and thermal measurements must be collected before the project chooses a
default model.

## Device gates

### A. Signature and permission boundary

PASS requires:
- Companion V2 installs;
- Book sender installs after Companion V2;
- signer SHA-256 digests match;
- shell-origin Book broadcast is rejected or permission-denied;
- Book sender ordered broadcast reports Activity.RESULT_OK.

### B. Book context

In Book Context Test Sender:
1. create a new test session;
2. send fresh context;
3. return to Companion V2.

PASS requires the Companion Book status to show synthetic-book, the current
section and mode learn.

Then send the next section; sequence 2 must replace the current context.
Then clear; Companion V2 must report no fresh Book context.

### C. 3714430278

Import the decrypted skin and verify first frame, idle, happy->smile,
sad->sad, surprised->surprise, unsupported emotion->safe idle, and
background/reopen.

### D. Local GGUF

Record model identity/hash, load time, RAM, first-token latency, approximate
generation speed, thermal state, and any crash/OOM.

### E. Voice input

Import the bilingual ASR package and press the voice button.

PASS requires RECORD_AUDIO to appear only after explicit use, no raw audio file
to be created, and final ASR text to be submitted to local llama.

### F. Local TTS

Import Melo TTS and explicitly enable speech replies.

PASS requires local playback, no generated wav persistence, disable behavior,
and stop-on-background.

### G. Memory and conversation

Verify:
- normal chat does not become explicit long-term memory;
- remember/update/history/forget work;
- forget purges active memory and its audit history;
- clear-chat clears recent visible conversation but not explicit memory;
- after model reload, recent chat is primed once as historical data.

## Acceptance rule

Do not merge PR #15 merely because a local build succeeds.

The accepted evidence package should include exact git head, APK hashes, signer
digest, package/permission dumps, model identities, Book positive/negative
results, memory/thermal snapshots, failures, screenshots and logs.


## Final evidence collection

After running the in-app benchmark and manual Book/voice/memory gates, run:

powershell -ExecutionPolicy Bypass -File .\android_llm_spike\scripts\collect_companion_v2_evidence.ps1

The collector writes current package state, meminfo, thermal state, activity state, process logcat, the app-private benchmark report when present, an app-private file listing, and a current screenshot into a gitignored device_evidence directory.
