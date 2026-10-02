# Existing llama JNI build gate · 2026-10-02

## Scope and acceptance boundary

This gate builds the existing `android_llm_spike` targets only:

- `:llama-lib:assembleRelease`
- `:bridge:assembleRelease`
- `:app:assembleDebug`

It adds no alternative LLM implementation or new Android project. It does not
configure Companion/Spine, Book sender/SDK or voice modules in this explicit CI
mode. Normal settings and local builds without `mygptNativeCi=true` retain their
existing modules and toolchain requirements. No GGUF, private skin, user data,
model inference, microphone, device, installation or distribution is involved.

A successful hosted run establishes actual native compilation/linking and
AAR/APK packaging for its exact source SHA. ARM64 payloads receive structural
class/JNI/ELF/dependency checks. The upstream library also configures/builds
x86_64, which is **not** counted as structurally verified or device-tested.
Neither JNI execution nor loadability on a physical device follows from these
static checks. Model quality, performance, Book adoption, voice, Companion,
Spine entitlement and combined device experience remain separate gates.

Local synthetic tests are tests of the verifier, not a native Android pass.
No exact-head hosted result for this edited candidate is recorded in this
change. Existing historical governance checkpoints are not promoted.

## Explicit CI toolchain integration

The llama source pin remains
`ba0ba54d93b25faf1e149f4ccedd3e9d84798563`. Only that git submodule is fetched;
there is no recursive sherpa checkout and upstream files are not patched.

Its original library asks for NDK `29.0.13113456`. The CI-only owned root Gradle
configuration uses Android Components `finalizeDsl` to select the runner's
already installed stable NDK `29.0.14206865`, with build-tools `36.0.0`. This
explicit integration override is in the output schema; success is not described
as a build with upstream's original NDK. AGP `8.13.2`, Kotlin `2.3.0`, Gradle
`8.14.3`, compile SDK 36, min SDK 33 and CMake `3.31.6` remain fixed.

The preflight reads actual runner paths, package identities/revisions, API level,
compiler versions and existing package license acceptance files. Each selected
SDK/build-tools/NDK package's exact license text SHA-1 must already be in its
existing `licenses/android-sdk-license`. This only reads an existing acceptance;
it does not accept or store a license. Missing/mismatched components or licenses
stop the job. JDK 17 and Ninja `1.13.2` must already be installed. No `sdkmanager`,
SDK installer, JDK installer, CMake downgrade or automatic license acceptance is
used. Both SDK and JDK automatic downloads are explicitly disabled for Gradle.

Global CMake's actual installation prefix is supplied through `cmake.dir` in
private runner-local `local.properties`, together with `sdk.dir`. Finalized DSL
records the SDK selected by AGP, plugin version, NDK, SDK levels, build-tools,
CMake version and ABI scope. The post-build check rechecks installed components
and licenses and reads the actual CMake caches' compiler, NDK, CMake, Ninja,
Android target and ABI configuration. Only caches whose `CMAKE_HOME_DIRECTORY`
is the exact pinned library `src/main/cpp` count; nested FetchContent host
sub-build caches are excluded, and both declared native ABIs remain required.
Merely being present on PATH is not
accepted as proof that the build selected a tool. `CMAKE_BUILD_TYPE` must be
`Release` or `Debug`; this check deliberately does not bind each CMake cache or
its optimization flags to an AGP variant. It does not verify Release optimization
level or performance. An all-Debug cache fixture is allowed when every other
exact toolchain, source-directory, API 33 and dual-ABI requirement holds. The
separate clean CI task/packaging gates still require both `assembleRelease`
targets and their release AARs, plus `assembleDebug` and its local APK. A release
artifact name is not evidence of native optimization flags.

Gradle is acquired by the same SHA-pinned `setup-gradle` action already used by
this project, not claimed to be preinstalled. Before the project runs, its
binary-only ZIP must match the official 8.14.3 SHA-256
`bd71102213493060956ec229d946beee57158dbd89d0e62b91bca0fa2c5f3531`.
Every installed distribution file must match that verified ZIP, with no extra
files. The setup action may first query the trusted runner's already installed
Gradle with `-v`; the checksum boundary applies to the acquired project
distribution before the project build, not to every preinstalled-tool version
probe. A missing ZIP never skips validation; the same official fixed ZIP URL
is fetched for verification. Gradle caches and public build scans are disabled.
The wrapper's distribution checksum is also fixed without replacing its JAR.

Normal declared Maven dependencies are still resolved. The pinned upstream
ARM64 CMake also fetches its existing public
[KleidiAI v1.24.0 source archive](https://github.com/ARM-software/kleidiai/releases/download/v1.24.0/kleidiai-v1.24.0-src.tar.gz),
using upstream's MD5 `2f02ebe29573d45813e671eb304f2a00`. The post-build check
requires that retained archive, verifies the upstream MD5 and records its actual
SHA-256. This does not turn an MD5-pinned upstream dependency or Maven resolution
into a fully SHA-256-locked dependency graph. No bit-identical binary claim is
made. Any new explicit legal agreement or paid step requires separate approval.

## Payload and publication contract

`verify_llama_payloads.py` reads the built library AAR, bridge AAR and local APK.
It rejects duplicate/invalid ZIP members and checks the selected members' CRCs.
It validates actual Java class identities in `classes.jar` and DEX class
identities, including `AiChat`, `InferenceEngine`, the native
`internal.InferenceEngineImpl`, owned bridge and application entrypoint. The
native implementation's method signatures must match the pinned JNI API.
ARM64 libraries must be little-endian ELF64 `ET_DYN`/AArch64 with the expected
actually defined JNI exports. Every packaged ARM64 `.so` is checked, and all
`DT_NEEDED` edges must resolve within the same package or to the explicit
Android system set (`libandroid`, `liblog`, `libc`, `libm`, `libdl`).
`libc++_shared.so`, `libomp.so` and other non-system dependencies must really be
packaged. The pin also loads CPU backends dynamically, so `DT_NEEDED` alone is
insufficient: both llama AAR and local APK must contain all seven ARM64 Android
CPU backend variants declared by the pin (`armv8.0_1`, `armv8.2_1`,
`armv8.2_2`, `armv8.6_1`, `armv9.0_1`, `armv9.2_1`, `armv9.2_2`, each with the
`libggml-cpu-android_` prefix and `.so` suffix). Each must export defined executable `ggml_backend_init` and
`ggml_backend_score`. These are the existing enabled upstream targets, not new
features. This checks package-level declared dynamic dependencies and known
backend presence; it is not Android loader execution or proof of arbitrary
runtime dependency completeness.
Unrelated asset/model member bodies are never inspected; their internal
structure/CRC is not part of this selected-payload check.

The former full-Companion workflow is replaced by a `workflow_call`-only build,
not reopened by merely correcting its old repository owner. The aggregate
`fusion-required-gate` requires `llama-native` in addition to all its existing
required components. Missing, skipped, cancelled and failed jobs fail closed.

Exactly one public artifact file is uploaded, `native-build-summary.json`, only
after success. It has a closed schema of fixed labels, source/upstream identity,
validated toolchain versions, boolean scope/result fields, numeric counts,
package sizes and SHA-256 values. No AAR, APK, model, source archive, raw build
log, absolute runner path or arbitrary input field is projected. Build logs and
path-bearing toolchain/DSL reports stay only in ephemeral runner storage.
Failures emit fixed diagnostic codes. Build failures additionally print only a
closed projection of fixed stage enums, known owned-file labels and numeric
line/column coordinates, plus the raw log's byte count and SHA-256. Unknown
failures stay `UNKNOWN`; raw text is never emitted or uploaded. This limited
evidence can classify a failure without claiming to reveal its full cause. This gate does not change the complete
double-build/source-recovery tests or their separate
`public-recovery-summary.json`-only publication contract.

## Verification

```sh
python -m unittest discover -s tests -p 'test_llama*.py' -v
python -m unittest discover -s tests -p 'test_*.py' -q
npm test
python brain/scripts/verify_integrations.py --output /new/private/strict
python brain/scripts/verify_fusion_upstreams.py --output /new/private/upstream
```

Negative fixtures include wrong/missing/unaccepted toolchains, tampered Gradle
archives/installations, configured-DSL and actual CMake path drift, no implicit
SDK/JDK download, missing/invalid classes/DEX/JNI/ELF/ABI, unresolved dynamic
libraries, duplicate payloads, undeclared public fields, private-data leakage
and missing/skipped native aggregate jobs. Fixtures do not download dependencies
or execute Android code.

References: [Android Components finalizeDsl](https://developer.android.com/reference/tools/gradle-api/8.13/com/android/build/api/variant/LibraryAndroidComponentsExtension),
[custom CMake installation](https://developer.android.com/studio/projects/install-ndk),
[official Gradle distribution checksums](https://gradle.org/release-checksums/),
[pinned setup-gradle provisioning](https://github.com/gradle/actions/blob/ed408507eac070d1f99cc633dbcf757c94c7933a/sources/src/execution/provision.ts).
