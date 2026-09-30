# Drive source identity for 3714430278 private bundle

The authenticated Drive hierarchy was verified as:

`My Drive / Live / skin / workshop / 3714430278 / 3714430278.zip`

Drive file id: `1B6AL3_3ymbOPSowiX-tGK-2QRXL_7Ozt`.

The raw Drive download was independently hashed before this path was added to
the Windows build allowlist:

`eb6eddc96172c03fe4d0dd4dd8a68180ce832aeb82ae07f7f82175fed57bc23f`

The build script still trusts the hash and byte count, not the path. A file at
that path with different bytes is rejected/ignored.

The final evidence collector should be run with the build's original
`-OutputDirectory` so bundled-skin, signature, Book, supervision, PiP, model
fingerprint, prompt-budget and benchmark evidence remain in one directory.
