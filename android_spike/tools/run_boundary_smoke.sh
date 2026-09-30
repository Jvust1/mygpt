#!/usr/bin/env bash
# Shared, source-only Java acceptance; never builds an APK or opens a device.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
: "${GSON_JAR:?Set GSON_JAR to the verified Gson 2.14.0 artifact}"
if test "${GITHUB_ACTIONS:-false}" = true && test "${MYGPT_JAVA_SOURCE_TARGET_ONLY:-0}" = 1; then
  echo "Source/target-only fallback is prohibited in hosted acceptance" >&2
  exit 2
fi
python android_spike/tools/verify_gson_artifact.py "$GSON_JAR"
python android_spike/tools/verify_lexical_integration.py
mkdir -p android_spike/build/classes
if test "${MYGPT_JAVA_SOURCE_TARGET_ONLY:-0}" = 1; then
  # Explicit local fallback for stripped JRE images that contain jdk.compiler
  # but no javac executable/ct.sym. This does NOT prove Java 8 API compatibility.
  JAVAC=(java -Xmx128m -m jdk.compiler/com.sun.tools.javac.Main)
  JAVAC_COMPAT=(-source 8 -target 8)
  echo "LOCAL SOURCE/TARGET ONLY: use hosted Java 8/17 gates for API/runtime proof"
else
  JAVAC=(javac)
  case "$(javac -version 2>&1)" in
    "javac 1.8."*) JAVAC_COMPAT=(-source 8 -target 8) ;;
    *) JAVAC_COMPAT=(--release 8) ;;
  esac
fi
"${JAVAC[@]}" "${JAVAC_COMPAT[@]}" -cp "$GSON_JAR" -d android_spike/build/classes \
  android_spike/src/main/java/dev/mygpt/spike/CompanionCoordinator.java \
  android_spike/src/main/java/dev/mygpt/spike/SkinCapabilityCatalog.java \
  android_spike/src/main/java/dev/mygpt/spike/PresentationEmotion.java \
  android_spike/src/main/java/dev/mygpt/spike/SpinePackageLayout.java \
  android_spike/src/main/java/dev/mygpt/spike/VoicePcm.java \
  android_spike/src/main/java/dev/mygpt/spike/LocalLlmEngine.java \
  android_spike/src/main/java/dev/mygpt/spike/SerializedLocalLlmEngine.java \
  android_spike/src/main/java/dev/mygpt/spike/FloatDragPolicy.java \
  android_spike/src/main/java/dev/mygpt/spike/AiriActEmotionParser.java \
  android_spike/src/main/java/dev/mygpt/spike/LexicalMemoryScorer.java \
  android_spike/src/main/java/dev/mygpt/spike/OnDeviceCompanionBrain.java \
  android_spike/src/main/java/dev/mygpt/spike/GgufModelProbe.java \
  android_spike/src/main/java/dev/mygpt/spike/GgufModelInstaller.java \
  android_spike/src/main/java/dev/mygpt/spike/BookContextSnapshot.java \
  android_spike/src/main/java/dev/mygpt/spike/BookContextMailbox.java \
  android_spike/src/main/java/dev/mygpt/spike/StudySupervisorRuntime.java \
  android_spike/src/main/java/dev/mygpt/spike/CompanionPromptBudget.java \
  android_spike/src/main/java/dev/mygpt/spike/LlmBenchmarkCandidateCatalog.java \
  android_llm_spike/book-client-sdk/src/main/java/dev/mygpt/bookbridge/BookCompanionContract.java \
  android_llm_spike/book-client-sdk/src/main/java/dev/mygpt/bookbridge/BookContextPayload.java \
  android_llm_spike/book-client-sdk/src/main/java/dev/mygpt/bookbridge/BookCompanionSession.java \
  android_voice_spike/app/src/main/java/dev/mygpt/voicespike/ModelFingerprintManifest.java \
  android_voice_spike/app/src/main/java/dev/mygpt/voicespike/SherpaModelIdentity.java \
  android_voice_spike/app/src/main/java/dev/mygpt/voicespike/AudioFloatResampler.java \
  android_spike/src/test/java/dev/mygpt/spike/CompanionCoordinatorSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/SpinePackageLayoutSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/SkinCapabilityCatalogSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/VoicePcmSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/LocalLlmEngineSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/FloatDragPolicySmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/OnDeviceCompanionBrainSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/AiriActGoldenSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/LexicalMemoryScorerSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/AiriHistoryBudgetSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/GgufModelProbeSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/GgufModelInstallerSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/BookContextMailboxSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/StudySupervisorRuntimeSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/CompanionPromptBudgetSmoke.java \
  android_spike/src/test/java/dev/mygpt/spike/LlmBenchmarkCandidateCatalogSmoke.java \
  android_llm_spike/book-client-sdk/src/test/java/dev/mygpt/bookbridge/BookClientSdkSmoke.java \
  android_voice_spike/app/src/test/java/dev/mygpt/voicespike/ModelFingerprintManifestSmoke.java \
  android_voice_spike/app/src/test/java/dev/mygpt/voicespike/SherpaModelIdentitySmoke.java \
  android_voice_spike/app/src/test/java/dev/mygpt/voicespike/AudioFloatResamplerSmoke.java
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.CompanionCoordinatorSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.SpinePackageLayoutSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.SkinCapabilityCatalogSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.VoicePcmSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.LocalLlmEngineSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.FloatDragPolicySmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.OnDeviceCompanionBrainSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.AiriActGoldenSmoke android_spike/src/test/resources/airi-act-golden.json
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.GgufModelProbeSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.GgufModelInstallerSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.BookContextMailboxSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.StudySupervisorRuntimeSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.CompanionPromptBudgetSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.LlmBenchmarkCandidateCatalogSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.bookbridge.BookClientSdkSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.voicespike.ModelFingerprintManifestSmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.voicespike.SherpaModelIdentitySmoke
java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.voicespike.AudioFloatResamplerSmoke

java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.LexicalMemoryScorerSmoke android_spike/src/test/resources/lexical-memory-golden.json

java -Xmx128m -cp "android_spike/build/classes:$GSON_JAR" dev.mygpt.spike.AiriHistoryBudgetSmoke android_spike/src/test/resources/airi-history-golden.json
