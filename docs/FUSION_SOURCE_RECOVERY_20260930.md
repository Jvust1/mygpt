# Recovery of the fused companion source

Base: integrated acceptance [PR #40](https://github.com/Jvust1/mygpt/pull/40),
`96e12e46ede0e72d9aeb3e6a6ffd0e142e9b332e`.

The existing recovery builder rejected this real tree: 161 paths now contain
Android sources, upstream licenses/notices, `.gitmodules`, a tracked Gradle
bootstrap jar and two pinned Gitlinks. It previously supported only the older
Python/web slice. Rejection was explicit; no prior complete archive is implied.

## Source scope and external dependencies

The v2 archive contains every supported tracked regular file at one exact commit,
including Android code and the licenses/notices for the fused AIRI, Pipecat,
Ollama, scikit-learn and Gson paths. The builder never copies the working tree,
loads private model/skin files, executes Gradle, clones or fetches a dependency.
An unsupported tracked path still rejects the whole build rather than being
silently dropped. Existing v1 archives remain verifiable.

Two Gitlinks are **metadata references only**, not dependency source archives:

- `ggml-org/llama.cpp`: `ba0ba54d93b25faf1e149f4ccedd3e9d84798563`
- `k2-fsa/sherpa-onnx`: `040afe360a38e25daaa325ce8889abf93ea02609`

Their canonical HTTPS URLs, paths and commits must match the explicit registry
and `.gitmodules`. Extra settings, command-based update hooks, URL changes,
missing notices and inclusion claims are rejected. No `.git` directory or
submodule working tree is archived. A recovered tree therefore cannot build the
Android JNI stack without separately obtaining its external pinned source and
toolchain. It also needs the declared Python/Maven dependencies.

The only permitted jar is the **already-tracked Gradle wrapper bootstrap** at
`android_llm_spike/gradle/wrapper/gradle-wrapper.jar`, SHA-256
`e996d452d2645e70c01c11143ca2d3742734a28da2bf61f25c82bdc288c9e637`.
Its existing origin record and Apache-2.0 launcher headers remain included. The
manifest identifies this binary separately; it is neither a model nor the Gson
runtime. Arbitrary jars, APK/AAR/native binaries, model formats, databases,
keystores, generated build/cache directories, fonts and secret paths stay denied.

The scope is tracked project source plus the recorded bootstrap, not a standalone
APK or an offline dependency-complete app. File/manifest hashes detect damage;
a trusted external archive SHA-256 remains necessary for authenticity. Recording
a source commit does not by itself prove that an untrusted ZIP came from GitHub.

## Actual recovery gate

The source-delivery workflow now uses the current `Jvust1/mygpt` owner and exact
push SHA. It:

1. Runs root regressions and builds the archive twice from that immutable commit
2. Requires byte-identical outputs, then verifies every member and manifest hash
3. Extracts into a new directory and confirms both external source trees are absent
4. Runs the recovered launcher/loopback shutdown probe, native selection intake,
   full strict Brain, root Python and JavaScript tests without original-project imports
5. Verifies the external Gson jar and runs all 18 recovered Java smoke entrypoints,
   including 327 Python/Gson cases, compiled with Java 17 `--release 8`

The workflow retains source and bounded test evidence for three days. It does not
accept Android SDK licenses, execute model inference, build/upload an APK or
connect to a device. Shared dependencies are installed once from the unchanged
hash lock; no second virtual environment or new runtime package is introduced.

## Reproduction

```sh
python scripts/source_bundle.py build --commit FULL_40_HEX_COMMIT --output /outside/repo/source.zip
python scripts/source_bundle.py verify /outside/repo/source.zip --sha256 TRUSTED_64_HEX_SHA256
```

Do not extract an archive before verification. The tool itself never extracts or
starts an application. Recovered Python execution and Java compilation require
the existing dependency/toolchain setup; external Gitlink references do not
pretend to supply those dependencies.

The immutable PR #40 tree was locally recovered with **389 tracked files** plus
its generated manifest, retaining both external references and all notices.
Exact final candidate counts, hashes and hosted execution belong in PR evidence,
not an invented self-referential commit value in this document.
