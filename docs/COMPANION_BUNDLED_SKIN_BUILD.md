# Optional self-contained 3714430278 Companion build

The approved decrypted Drive package is:

- file: `3714430278.zip`
- Drive file id: `1B6AL3_3ymbOPSowiX-tGK-2QRXL_7Ozt`
- bytes: `12342220`
- SHA-256: `eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f`

That digest matches `SpinePackageLayout.EXPECTED_ARCHIVE_SHA256`. Runtime
installation still verifies the archive and all 13 required core-file digests.

The ZIP is **not** committed to Git.

## Windows build injection

`build_and_install_companion_v2.ps1` looks for a private local source in this
order:

1. explicit `-SkinZip <path>`;
2. `MYGPT_SKIN_ZIP` environment variable;
3. a small allowlisted set of Google Drive Desktop paths on mounted filesystem
   roots / the user profile.

It never recursively scans a drive.

Before copying, the script requires both exact byte length and exact SHA-256.
The validated ZIP is copied only into:

`android_llm_spike/companion/build/generated/bundled-skin-assets/3714430278.zip`

The generated directory is removed at the beginning of each build, preventing a
stale private asset from leaking into a later unbundled build.

After APK build, the script opens the APK, locates
`assets/3714430278.zip`, recomputes SHA-256 from the APK entry stream, and
requires the same fixed digest. Evidence records hash/size/mode but not the local
Drive filesystem path.

## Runtime

On startup Companion V2:
1. validates an already-installed app-private skin if present;
2. otherwise attempts to install bundled `assets/3714430278.zip`;
3. the normal production `SpinePackageLayout.install()` exact archive and
   per-file digest gates still apply;
4. if no bundled asset exists, the manual SAF picker remains available.

A self-contained Windows build therefore reaches skin-ready/PiP without manual
file selection. GitHub CI remains capable of an unbundled build because the
generated asset is optional.
