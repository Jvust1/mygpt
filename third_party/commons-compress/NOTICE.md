# Apache Commons Compress attribution

Dependency: `org.apache.commons:commons-compress:1.28.0`  
Project: https://commons.apache.org/proper/commons-compress/  
License: Apache-2.0

MyGPT uses Commons Compress only as a dependency for bounded streaming reads of
official model archives in ZIP, TAR.BZ2 and TAR.GZ form.

Local integration:
- `android_voice_spike/app/src/main/java/dev/mygpt/voicespike/ModelArchiveReader.java`

Extraction policy remains MyGPT-owned:
- callers select only strict basename allowlists;
- arbitrary archive paths are never materialized;
- model installers enforce per-file and total decompressed size limits;
- imported README/LICENSE files are retained when present.

No Apache Commons Compress source code is copied into MyGPT.
