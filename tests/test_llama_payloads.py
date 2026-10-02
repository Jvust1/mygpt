"""Pure-byte parser fixtures only: no compiler, Android build or native execution.

Passing these tests proves fail-closed artifact inspection, not that a native
ARM64 build or device inference passed. No real model, skin or user data is used.
"""
from pathlib import Path
import copy
import hashlib
import io
import json
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_llama_payloads as verify


def classfile(name, *, native_access=0x102, jni_methods=None):
    pool = []
    def utf8(text):
        raw = text.encode("ascii")
        pool.append(b"\x01" + struct.pack(">H", len(raw)) + raw)
        return len(pool)
    utf8(name)
    pool.append(b"\x07\x00\x01")
    utf8("java/lang/Object")
    pool.append(b"\x07\x00\x03")
    methods = []
    if name == verify.JNI_CLASS:
        for method, signature in (verify.JNI_METHODS if jni_methods is None else jni_methods).items():
            name_id, signature_id = utf8(method), utf8(signature)
            methods.append(struct.pack(">HHHH", native_access, name_id, signature_id, 0))
    return (b"\xca\xfe\xba\xbe" + struct.pack(">HHH", 0, 61, len(pool) + 1) + b"".join(pool)
            + struct.pack(">6H", 0x21, 2, 4, 0, 0, len(methods)) + b"".join(methods) + b"\0\0")


def archive_bytes(entries):
    output = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, raw in entries:
                archive.writestr(name, raw)
    return output.getvalue()


def jar(classes):
    return archive_bytes((name + ".class", classfile(name)) for name in sorted(classes))


def elf(exports=(), needed=(), *, symbol_kind=2, binding=1, visibility=0, defined=True):
    """Synthetic ELF64 fixture with mapped sections, dynamic table and ARM64 RET bytes."""
    exports = sorted(exports)
    text_off = 176
    text = b"\xc0\x03\x5f\xd6" * max(1, len(exports))
    strings = bytearray(b"\0")
    offsets = {}
    for name in list(exports) + list(needed):
        offsets[name] = len(strings)
        strings.extend(name.encode("ascii") + b"\0")
    dynstr_off = text_off + len(text)
    dynsym_off = (dynstr_off + len(strings) + 7) & ~7
    symbols = b"\0" * 24
    for index, name in enumerate(exports):
        symbols += struct.pack("<IBBHQQ", offsets[name], binding << 4 | symbol_kind, visibility,
                               1 if defined else 0, text_off + 4 * index, 4)
    dynamic_off = dynsym_off + len(symbols)
    tags = [(1, offsets[name]) for name in needed] + [(5, dynstr_off), (6, dynsym_off),
            (10, len(strings)), (11, 24), (0, 0)]
    dynamic = b"".join(struct.pack("<qQ", tag, value) for tag, value in tags)
    names = b"\0.text\0.dynstr\0.dynsym\0.dynamic\0.shstrtab\0"
    names_off = dynamic_off + len(dynamic)
    shoff = (names_off + len(names) + 7) & ~7
    data = bytearray(shoff + 6 * 64)
    ident = b"\x7fELF\x02\x01\x01" + b"\0" * 9
    header = struct.pack("<HHIQQQIHHHHHH", 3, 183, 1, 0, 64, shoff, 0, 64, 56, 2, 64, 6, 5)
    data[:64] = ident + header
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0, 0, shoff, shoff, 4096)
    struct.pack_into("<IIQQQQQQ", data, 120, 2, 4, dynamic_off, dynamic_off, dynamic_off,
                     len(dynamic), len(dynamic), 8)
    for offset, raw in ((text_off, text), (dynstr_off, strings), (dynsym_off, symbols),
                         (dynamic_off, dynamic), (names_off, names)):
        data[offset:offset + len(raw)] = raw
    sections = [(0,) * 10,
                (1, 1, 6, text_off, text_off, len(text), 0, 0, 4, 0),
                (7, 3, 2, dynstr_off, dynstr_off, len(strings), 0, 0, 1, 0),
                (15, 11, 2, dynsym_off, dynsym_off, len(symbols), 2, 1, 8, 24),
                (23, 6, 2, dynamic_off, dynamic_off, len(dynamic), 2, 0, 8, 16),
                (32, 3, 0, 0, names_off, len(names), 0, 0, 1, 0)]
    for index, section in enumerate(sections):
        struct.pack_into("<IIQQQQIIQQ", data, shoff + index * 64, *section)
    return bytes(data)


def uleb128(value):
    raw = bytearray()
    while value >= 128:
        raw.append((value & 127) | 128)
        value >>= 7
    raw.append(value)
    return bytes(raw)


def dex(classes, *, native_access=0x102, jni_methods=None):
    """Minimal checksum-correct DEX with real class_defs/native methods, never executed."""
    descriptors = sorted("L" + name + ";" for name in classes)
    jni_descriptor = "L" + verify.JNI_CLASS + ";"
    native = (verify.JNI_METHODS if jni_methods is None else jni_methods) if jni_descriptor in descriptors else {}
    method_names = sorted(native)
    signatures = sorted(set(native.values()))
    parameters = {signature: re.findall(r"Ljava/lang/String;|[IV]", signature.split(")")[0][1:])
                  for signature in signatures}
    returns = {signature: signature.split(")")[1] for signature in signatures}
    shorties = {signature: returns[signature][0] + "".join(value[0] for value in parameters[signature])
                for signature in signatures}
    types = sorted(set(descriptors) | set(returns.values()) |
                   {value for values in parameters.values() for value in values})
    strings = sorted(set(types) | set(method_names) | set(shorties.values()))
    sid = {name: index for index, name in enumerate(strings)}
    tid = {name: index for index, name in enumerate(types)}
    strings_off = 112
    types_off = strings_off + len(strings) * 4
    protos_off = types_off + len(types) * 4
    methods_off = protos_off + len(signatures) * 12
    classes_off = methods_off + len(method_names) * 8
    data_off = classes_off + len(descriptors) * 32
    body = bytearray(data_off)
    body[:8] = b"dex\n039\0"
    strings_data_off = len(body)
    for index, value in enumerate(strings):
        struct.pack_into("<I", body, strings_off + index * 4, len(body))
        body.extend(uleb128(len(value)) + value.encode("ascii") + b"\0")
    for index, value in enumerate(types):
        struct.pack_into("<I", body, types_off + index * 4, sid[value])
    body.extend(b"\0" * (-len(body) % 4))
    type_lists_start = len(body)
    type_list_count = 0
    for index, signature in enumerate(signatures):
        args = parameters[signature]
        parameter_off = 0
        if args:
            parameter_off = len(body)
            body.extend(struct.pack("<I", len(args)))
            body.extend(b"".join(struct.pack("<H", tid[arg]) for arg in args))
            body.extend(b"\0" * (-len(body) % 4))
            type_list_count += 1
        struct.pack_into("<III", body, protos_off + index * 12,
                         sid[shorties[signature]], tid[returns[signature]], parameter_off)
    class_data_off = len(body)
    if native:
        body.extend(uleb128(0) + uleb128(0) + uleb128(len(method_names)) + uleb128(0))
        for index, method in enumerate(method_names):
            struct.pack_into("<HHI", body, methods_off + index * 8,
                             tid[jni_descriptor], signatures.index(native[method]), sid[method])
            body.extend(uleb128(0 if index == 0 else 1) + uleb128(native_access) + uleb128(0))
    for index, descriptor in enumerate(descriptors):
        struct.pack_into("<8I", body, classes_off + index * 32, tid[descriptor], 1, 0xffffffff, 0,
                         0xffffffff, 0, class_data_off if descriptor == jni_descriptor and native else 0, 0)
    body.extend(b"\0" * (-len(body) % 4))
    map_off = len(body)
    entries = [(0, 1, 0), (1, len(strings), strings_off), (2, len(types), types_off),
               (6, len(descriptors), classes_off), (0x2002, len(strings), strings_data_off),
               (0x1000, 1, map_off)]
    if native:
        entries += [(3, len(signatures), protos_off), (5, len(method_names), methods_off),
                    (0x2000, 1, class_data_off)]
    if type_list_count:
        entries.append((0x1001, type_list_count, type_lists_start))
    body.extend(struct.pack("<I", len(entries)))
    for kind, size, offset in sorted(entries, key=lambda row: row[2]):
        body.extend(struct.pack("<HHII", kind, 0, size, offset))
    struct.pack_into("<20I", body, 32, len(body), 112, 0x12345678, 0, 0, map_off,
                     len(strings), strings_off, len(types), types_off,
                     len(signatures), protos_off if native else 0, 0, 0,
                     len(method_names), methods_off if native else 0,
                     len(descriptors), classes_off, len(body) - data_off, data_off)
    return resign_dex(body)


def resign_dex(data):
    data = bytearray(data)
    data[12:32] = hashlib.sha1(data[32:]).digest()
    struct.pack_into("<I", data, 8, zlib.adler32(data[12:]) & 0xffffffff)
    return bytes(data)


class LlamaPayloadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="synthetic-llama-parser-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.paths = {name: self.root / name for name in ("llama_aar", "bridge_aar", "local_apk")}
        self.toolchain = {**verify.TOOLCHAIN_CONSTANTS, "java_version": "17.0.17",
                          "kleidiai_archive_sha256": "b" * 64}
        self.entries = {
            "llama_aar": [("classes.jar", jar(verify.LLAMA_CLASSES)),
                          ("jni/arm64-v8a/libai-chat.so", elf(verify.JNI_EXPORTS, ["liblog.so", "libc.so"]))],
            "bridge_aar": [("classes.jar", jar(verify.BRIDGE_CLASSES))],
            "local_apk": [("classes.dex", dex(verify.APK_CLASSES)),
                          ("lib/arm64-v8a/libai-chat.so", elf(verify.JNI_EXPORTS, ["liblog.so", "libc.so"]))],
        }
        for kind, prefix in (("llama_aar", "jni/arm64-v8a/"), ("local_apk", "lib/arm64-v8a/")):
            self.entries[kind] += [(prefix + name, elf(verify.BACKEND_EXPORTS, ["libc.so"]))
                                   for name in sorted(verify.ARM64_BACKENDS)]
        self.write()

    def write(self):
        for name, entries in self.entries.items():
            self.paths[name].write_bytes(archive_bytes(entries))

    def inspect(self):
        return verify.inspect_artifacts(**self.paths, source_commit="a" * 40, toolchain=self.toolchain)

    def rejected(self, code):
        self.write()
        with self.assertRaisesRegex(verify.PayloadError, "^" + code + "$"):
            self.inspect()

    def replace(self, artifact, name, raw):
        self.entries[artifact] = [(key, raw if key == name else value)
                                  for key, value in self.entries[artifact]]

    def test_synthetic_structure_passes_with_exact_closed_summary(self):
        report = self.inspect()
        self.assertEqual(report["scope"], "ARM64_COMPILE_LINK_PACKAGE_ONLY")
        self.assertEqual(report["upstream_commit"], verify.UPSTREAM_COMMIT)
        self.assertFalse(report["inference_executed"])
        self.assertFalse(report["physical_device_accepted"])
        self.assertEqual(report["artifacts"]["llama_aar"]["required_classes"], 3)
        self.assertEqual(report["artifacts"]["local_apk"]["required_jni_exports"], 10)
        self.assertEqual(report["artifacts"]["bridge_aar"]["arm64_libraries"], 0)
        for name, path in self.paths.items():
            self.assertEqual(report["artifacts"][name]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_source_commit_rejected_before_files_are_read(self):
        for source in ("", "HEAD", "A" * 40, "a" * 39, "a" * 41, "a" * 40 + "\n", None, True,
                       "PRIVATE_SOURCE_SENTINEL"):
            with self.subTest(source=source), mock.patch.object(Path, "read_bytes", side_effect=AssertionError):
                with self.assertRaisesRegex(verify.PayloadError, "^INVALID_SOURCE$"):
                    verify.inspect_artifacts(**self.paths, source_commit=source, toolchain=self.toolchain)

    def test_toolchain_rejects_missing_extra_wrong_types_and_unpinned_values(self):
        for key in self.toolchain:
            for action in ("missing", "wrong"):
                value = dict(self.toolchain)
                if action == "missing":
                    del value[key]
                else:
                    value[key] = "PRIVATE_VALUE"
                with self.subTest(key=key, action=action):
                    with self.assertRaisesRegex(verify.PayloadError, "^INVALID_TOOLCHAIN$"):
                        verify.validate_toolchain(value)
        for value in ({**self.toolchain, "extra": "PRIVATE_VALUE"},
                      {**self.toolchain, "sdk": True}, {**self.toolchain, "java_version": "17.0.17+7"},
                      {**self.toolchain, "java_version": "17.0.17\n"}):
            with self.assertRaises(verify.PayloadError):
                verify.validate_toolchain(value)

    def test_summary_is_closed_at_every_level_and_rejects_boolean_counts(self):
        original = self.inspect()
        for location in ((), ("toolchain",), ("artifacts",), ("artifacts", "llama_aar")):
            changed = copy.deepcopy(original)
            target = changed
            for key in location:
                target = target[key]
            target["PRIVATE_EXTRA"] = "PRIVATE_VALUE"
            with self.subTest(location=location), self.assertRaises(verify.PayloadError):
                verify.validate_summary(changed)
        for key in verify.ARTIFACT_KEYS - {"sha256"}:
            changed = copy.deepcopy(original)
            changed["artifacts"]["local_apk"][key] = True
            with self.subTest(key=key), self.assertRaises(verify.PayloadError):
                verify.validate_summary(changed)

    def test_each_required_aar_class_is_required(self):
        for kind, classes in (("llama_aar", verify.LLAMA_CLASSES), ("bridge_aar", verify.BRIDGE_CLASSES)):
            original = self.entries[kind][:]
            for missing in classes:
                with self.subTest(missing=missing):
                    self.entries[kind] = original[:]
                    self.replace(kind, "classes.jar", jar(classes - {missing}))
                    # Empty ZIP is rejected even before the missing-class check.
                    self.rejected("CLASS_MISSING" if len(classes) > 1 else "ZIP_LIMIT")
            self.entries[kind] = original

    def test_class_magic_identity_and_truncation_are_checked(self):
        required = "com/arm/aichat/AiChat"
        for bad in (b"not class", b"\xca\xfe\xba\xbe", classfile(required)[:-1], classfile("wrong/Identity")):
            with self.subTest(size=len(bad)):
                entries = [(name + ".class", bad if name == required else classfile(name))
                           for name in verify.LLAMA_CLASSES]
                self.replace("llama_aar", "classes.jar", archive_bytes(entries))
                self.rejected("CLASS_INVALID")

    def test_classes_jar_must_exist_and_not_be_plain_bytes(self):
        self.entries["bridge_aar"] = [("placeholder.txt", b"x")]
        self.rejected("PAYLOAD_MISSING")
        self.entries["bridge_aar"] = [("classes.jar", b"PRIVATE_BAD_JAR")]
        self.rejected("ZIP_INVALID")

    def test_aar_native_methods_need_exact_signatures_and_instance_native_flags(self):
        cases = [{"native_access": 0x2}, {"native_access": 0x10a}, {"jni_methods": {}},
                 {"jni_methods": {**verify.JNI_METHODS, "init": "()V"}}]
        for kwargs in cases:
            entries = [(name + ".class", classfile(name, **kwargs) if name == verify.JNI_CLASS else classfile(name))
                       for name in verify.LLAMA_CLASSES]
            self.replace("llama_aar", "classes.jar", archive_bytes(entries))
            with self.subTest(kwargs=kwargs):
                self.rejected("JNI_DECLARATION_MISSING")

    def test_apk_native_methods_need_exact_signatures_and_instance_native_flags(self):
        for kwargs in ({"native_access": 0x2}, {"native_access": 0x10a}, {"jni_methods": {}},
                       {"jni_methods": {**verify.JNI_METHODS, "load": "()I"}}):
            self.replace("local_apk", "classes.dex", dex(verify.APK_CLASSES, **kwargs))
            with self.subTest(kwargs=kwargs):
                self.rejected("JNI_DECLARATION_MISSING")

    def test_each_apk_native_method_is_required(self):
        for missing in verify.JNI_METHODS:
            methods = {name: signature for name, signature in verify.JNI_METHODS.items() if name != missing}
            self.replace("local_apk", "classes.dex", dex(verify.APK_CLASSES, jni_methods=methods))
            with self.subTest(missing=missing):
                self.rejected("JNI_DECLARATION_MISSING")

    def test_dex_map_must_match_actual_header_tables(self):
        bad = bytearray(dex(verify.APK_CLASSES))
        map_off, = struct.unpack_from("<I", bad, 52)
        struct.pack_into("<I", bad, map_off + 8, 999)
        self.replace("local_apk", "classes.dex", resign_dex(bad))
        self.rejected("DEX_INVALID")

    def test_each_required_apk_class_is_a_real_definition(self):
        for missing in verify.APK_CLASSES:
            with self.subTest(missing=missing):
                self.replace("local_apk", "classes.dex", dex(verify.APK_CLASSES - {missing}))
                self.rejected("DEX_CLASS_MISSING")

    def test_dex_decoy_strings_do_not_satisfy_classes(self):
        bad = bytearray(dex({"unrelated/OnlyClass"}))
        # A raw string occurrence outside the actual class definition is insufficient.
        bad.extend(b"Lcom/arm/aichat/AiChat;\0Ldev/mygpt/llama/LlamaCppCompanionEngine;\0")
        struct.pack_into("<I", bad, 32, len(bad))
        data_off, = struct.unpack_from("<I", bad, 108)
        struct.pack_into("<I", bad, 104, len(bad) - data_off)
        self.replace("local_apk", "classes.dex", resign_dex(bad))
        self.rejected("DEX_CLASS_MISSING")

    def test_dex_header_checksum_signature_tables_and_indices_are_checked(self):
        original = dex(verify.APK_CLASSES)
        for offset, raw, resign in ((0, b"fake", False), (8, b"\0" * 4, False),
                                   (12, b"\0" * 20, False), (36, struct.pack("<I", 0), True),
                                   (40, struct.pack("<I", 0x78563412), True),
                                   (60, struct.pack("<I", 0xffffffff), True),
                                   (112, struct.pack("<I", 0xffffffff), True)):
            bad = bytearray(original)
            bad[offset:offset + len(raw)] = raw
            with self.subTest(offset=offset):
                self.replace("local_apk", "classes.dex", resign_dex(bad) if resign else bytes(bad))
                self.rejected("DEX_INVALID")

    def test_multidex_class_definitions_are_combined(self):
        first = set(sorted(verify.APK_CLASSES)[:2])
        self.replace("local_apk", "classes.dex", dex(first))
        self.entries["local_apk"].append(("classes2.dex", dex(verify.APK_CLASSES - first)))
        self.write()
        self.assertEqual(self.inspect()["artifacts"]["local_apk"]["dex_files"], 2)

    def test_duplicate_classes_across_dex_are_rejected(self):
        self.entries["local_apk"].append(("classes2.dex", dex(verify.APK_CLASSES)))
        self.rejected("DEX_INVALID")

    def test_missing_apk_dex_or_native_payload_is_rejected(self):
        for kind, member in (("local_apk", "classes.dex"), ("local_apk", "lib/arm64-v8a/libai-chat.so"),
                              ("llama_aar", "jni/arm64-v8a/libai-chat.so")):
            original = self.entries[kind]
            self.entries[kind] = [(key, raw) for key, raw in original if key != member]
            with self.subTest(kind=kind, member=member):
                self.rejected("PAYLOAD_MISSING")
            self.entries[kind] = original

    def test_fake_elf_and_wrong_class_endian_machine_and_type_fail(self):
        original = elf(verify.JNI_EXPORTS)
        cases = [(b"fakeELF", "ELF_INVALID"), (original[:64], "ELF_INVALID")]
        for offset, raw, code in ((4, b"\x01", "ELF_ABI"), (5, b"\x02", "ELF_ABI"),
                                  (18, struct.pack("<H", 62), "ELF_ABI"),
                                  (16, struct.pack("<H", 1), "ELF_TYPE")):
            bad = bytearray(original)
            bad[offset:offset + len(raw)] = raw
            cases.append((bytes(bad), code))
        for bad, code in cases:
            with self.subTest(code=code, size=len(bad)):
                self.replace("llama_aar", "jni/arm64-v8a/libai-chat.so", bad)
                self.rejected(code)

    def test_all_ten_exact_defined_jni_exports_are_required(self):
        for missing in verify.JNI_EXPORTS:
            self.replace("llama_aar", "jni/arm64-v8a/libai-chat.so", elf(verify.JNI_EXPORTS - {missing}))
            with self.subTest(missing=missing):
                self.rejected("JNI_EXPORT_MISSING")

    def test_undefined_hidden_local_and_object_symbols_cannot_satisfy_jni(self):
        for kwargs in ({"defined": False}, {"visibility": 2}, {"binding": 0}, {"symbol_kind": 1}):
            with self.subTest(kwargs=kwargs):
                self.replace("llama_aar", "jni/arm64-v8a/libai-chat.so", elf(verify.JNI_EXPORTS, **kwargs))
                self.rejected("JNI_EXPORT_MISSING")

    def test_symbol_name_bytes_without_dynamic_symbols_do_not_pass(self):
        fake = elf() + b"\0".join(name.encode("ascii") for name in verify.JNI_EXPORTS)
        self.replace("local_apk", "lib/arm64-v8a/libai-chat.so", fake)
        self.rejected("JNI_EXPORT_MISSING")

    def test_unmapped_and_zero_sized_jni_code_does_not_pass(self):
        original = elf(verify.JNI_EXPORTS)
        shoff, = struct.unpack_from("<Q", original, 40)
        symbols, = struct.unpack_from("<Q", original, shoff + 3 * 64 + 24)
        for offset, value in ((symbols + 24 + 8, 0xffffffffffffffff), (symbols + 24 + 16, 0)):
            bad = bytearray(original)
            struct.pack_into("<Q", bad, offset, value)
            self.replace("llama_aar", "jni/arm64-v8a/libai-chat.so", bytes(bad))
            self.rejected("JNI_EXPORT_MISSING")

    def test_malformed_elf_tables_and_dynamic_metadata_fail_closed(self):
        original = elf(verify.JNI_EXPORTS)
        shoff, = struct.unpack_from("<Q", original, 40)
        for offset, raw in ((40, struct.pack("<Q", len(original))),
                            (58, struct.pack("<H", 1)),
                            (shoff + 3 * 64 + 40, struct.pack("<I", 500)),
                            (shoff + 4 * 64 + 56, struct.pack("<Q", 0))):
            bad = bytearray(original)
            bad[offset:offset + len(raw)] = raw
            self.replace("llama_aar", "jni/arm64-v8a/libai-chat.so", bytes(bad))
            with self.subTest(offset=offset):
                self.rejected("ELF_INVALID")

    def test_narrow_system_allowlist_excludes_cpp_omp_and_similar_names(self):
        for dependency in ("libc++_shared.so", "libomp.so", "libc-private.so", "libsecret.so"):
            self.replace("llama_aar", "jni/arm64-v8a/libai-chat.so", elf(verify.JNI_EXPORTS, [dependency]))
            with self.subTest(dependency=dependency):
                self.rejected("NATIVE_DEPENDENCY_MISSING")

    def test_cpp_omp_and_transitive_dependencies_must_be_packaged_per_archive(self):
        for kind, prefix in (("llama_aar", "jni/arm64-v8a/"), ("local_apk", "lib/arm64-v8a/")):
            self.replace(kind, prefix + "libai-chat.so", elf(verify.JNI_EXPORTS, ["libc++_shared.so", "libomp.so"]))
            self.entries[kind] += [(prefix + "libc++_shared.so", elf(needed=["libc.so"])),
                                   (prefix + "libomp.so", elf(needed=["libc++_shared.so", "libdl.so"]))]
        self.write()
        self.assertEqual(self.inspect()["artifacts"]["local_apk"]["arm64_libraries"], 10)
        self.replace("local_apk", "lib/arm64-v8a/libomp.so", elf(needed=["libmissing.so"]))
        self.rejected("NATIVE_DEPENDENCY_MISSING")

    def test_all_seven_dlopen_backends_are_required_in_aar_and_apk(self):
        for kind, prefix in (("llama_aar", "jni/arm64-v8a/"), ("local_apk", "lib/arm64-v8a/")):
            original = self.entries[kind][:]
            for missing in verify.ARM64_BACKENDS:
                self.entries[kind] = [(name, raw) for name, raw in original if name != prefix + missing]
                with self.subTest(kind=kind, missing=missing):
                    self.rejected("BACKEND_MISSING")
            self.entries[kind] = original

    def test_each_backend_requires_both_defined_callable_exports(self):
        for kind, prefix in (("llama_aar", "jni/arm64-v8a/"), ("local_apk", "lib/arm64-v8a/")):
            original = self.entries[kind][:]
            for backend in verify.ARM64_BACKENDS:
                for missing in verify.BACKEND_EXPORTS:
                    self.entries[kind] = original[:]
                    self.replace(kind, prefix + backend, elf(verify.BACKEND_EXPORTS - {missing}))
                    with self.subTest(kind=kind, backend=backend, missing=missing):
                        self.rejected("BACKEND_EXPORT_MISSING")
            self.entries[kind] = original

    def test_backend_export_bytes_undefined_hidden_local_or_object_do_not_pass(self):
        target = "lib/arm64-v8a/" + sorted(verify.ARM64_BACKENDS)[0]
        for kwargs in ({"defined": False}, {"visibility": 2}, {"binding": 0}, {"symbol_kind": 1}):
            self.replace("local_apk", target, elf(verify.BACKEND_EXPORTS, **kwargs))
            with self.subTest(kwargs=kwargs):
                self.rejected("BACKEND_EXPORT_MISSING")
        decoy = elf() + b"ggml_backend_init\0ggml_backend_score\0"
        self.replace("local_apk", target, decoy)
        self.rejected("BACKEND_EXPORT_MISSING")

    def test_every_extra_arm64_library_is_validated(self):
        for kind, prefix in (("llama_aar", "jni/arm64-v8a/"), ("bridge_aar", "jni/arm64-v8a/"),
                              ("local_apk", "lib/arm64-v8a/")):
            original = self.entries[kind][:]
            self.entries[kind].append((prefix + "libunreferenced.so", b"fake ELF"))
            with self.subTest(kind=kind):
                self.rejected("ELF_INVALID")
            self.entries[kind] = original

    def test_duplicate_outer_and_nested_zip_names_fail(self):
        self.entries["local_apk"].append(self.entries["local_apk"][0])
        self.rejected("ZIP_DUPLICATE")
        self.entries["local_apk"].pop()
        name = "dev/mygpt/llama/LlamaCppCompanionEngine"
        self.replace("bridge_aar", "classes.jar", archive_bytes([(name + ".class", classfile(name))] * 2))
        self.rejected("ZIP_DUPLICATE")

    def test_corrupted_selected_member_crc_and_bad_archive_fail(self):
        raw = bytearray(self.paths["llama_aar"].read_bytes())
        offset = raw.index(b"\x7fELF")
        raw[offset + 10] ^= 1
        self.paths["llama_aar"].write_bytes(raw)
        with self.assertRaisesRegex(verify.PayloadError, "^ZIP_INVALID$"):
            self.inspect()
        self.paths["llama_aar"].write_bytes(b"PRIVATE_INVALID_ZIP")
        with self.assertRaisesRegex(verify.PayloadError, "^ZIP_INVALID$"):
            self.inspect()

    def test_unsafe_member_names_fail_even_without_extraction(self):
        for name in ("../PRIVATE", "/PRIVATE", "assets/../PRIVATE", "assets\\PRIVATE", "assets//PRIVATE"):
            self.entries["local_apk"].append((name, b"private"))
            with self.subTest(name=name):
                self.rejected("ZIP_MEMBER_INVALID")
            self.entries["local_apk"].pop()

    def test_assets_are_never_decompressed_or_projected(self):
        sentinel = "PRIVATE_ASSET_SENTINEL"
        self.entries["local_apk"].append(("assets/" + sentinel + ".gguf", sentinel.encode()))
        self.write()
        original_read = zipfile.ZipFile.read
        selected = []
        def guarded_read(archive, name, *args, **kwargs):
            selected.append(name)
            self.assertNotIn("assets/", name)
            return original_read(archive, name, *args, **kwargs)
        with mock.patch.object(zipfile.ZipFile, "read", guarded_read):
            result = self.inspect()
        encoded = json.dumps(result)
        for secret in (sentinel, str(self.root), "classes.jar", "libai-chat.so"):
            self.assertNotIn(secret, encoded)
        self.assertGreater(len(selected), 5)

    def test_cli_success_emits_only_public_summary(self):
        config = self.root / "toolchain.json"
        config.write_text(json.dumps(self.toolchain))
        output = self.root / "public.json"
        result = self.cli(config, output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), {"status": "PASS"})
        self.assertEqual(result.stderr, "")
        verify.validate_summary(json.loads(output.read_text()))

    def test_cli_creates_missing_output_parents_then_failed_rerun_removes_pass(self):
        config = self.root / "toolchain.json"
        config.write_text(json.dumps(self.toolchain))
        output = self.root / "fresh" / "nested" / "native-build-summary.json"
        self.assertFalse(output.parent.exists())
        result = self.cli(config, output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        verify.validate_summary(json.loads(output.read_text()))
        self.paths["llama_aar"].write_bytes(b"PRIVATE_BAD_AAR")
        failed = self.cli(config, output)
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(json.loads(failed.stdout), {"status": "FAIL", "error": "ZIP_INVALID"})
        self.assertFalse(output.exists())
        self.assertEqual(list(output.parent.iterdir()), [])
        self.assertNotIn("PRIVATE_BAD_AAR", failed.stdout + failed.stderr)

    def cli(self, config, output, extra=()):
        return subprocess.run([sys.executable, str(ROOT / "scripts/verify_llama_payloads.py"),
                               "--llama-aar", str(self.paths["llama_aar"]),
                               "--bridge-aar", str(self.paths["bridge_aar"]),
                               "--apk", str(self.paths["local_apk"]), "--source-commit", "a" * 40,
                               "--toolchain-json", str(config), "--output", str(output), *extra],
                              text=True, capture_output=True)

    def test_cli_failure_redacts_errors_paths_and_removes_stale_success(self):
        sentinel = "PRIVATE_PATH_AND_CONTENT_SENTINEL"
        config = self.root / (sentinel + ".json")
        output = self.root / "public.json"
        for raw in ("{" + sentinel, json.dumps({**self.toolchain, "extra": sentinel})):
            config.write_text(raw)
            output.write_text('{"status":"PASS"}')
            result = self.cli(config, output)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())
            self.assertEqual(result.stderr, "")
            self.assertNotIn(sentinel, result.stdout)
            self.assertNotIn(str(self.root), result.stdout)
            self.assertIn(json.loads(result.stdout)["error"], verify.ERROR_CODES)

    def test_cli_duplicate_toolchain_fields_fail_and_unknown_args_are_redacted(self):
        config = self.root / "toolchain.json"
        config.write_text(json.dumps(self.toolchain)[:-1] + ',"sdk":36}')
        output = self.root / "public.json"
        self.assertEqual(json.loads(self.cli(config, output).stdout)["error"], "INVALID_TOOLCHAIN")
        result = self.cli(config, output, ["--PRIVATE_ARGUMENT_SENTINEL"])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), {"status": "FAIL", "error": "CLI_INVALID"})
        self.assertEqual(result.stderr, "")

    def test_output_cannot_replace_an_input(self):
        config = self.root / "toolchain.json"
        config.write_text(json.dumps(self.toolchain))
        original = self.paths["llama_aar"].read_bytes()
        result = self.cli(config, self.paths["llama_aar"])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.paths["llama_aar"].read_bytes(), original)

    def test_output_temporary_does_not_overwrite_existing_neighbor(self):
        config = self.root / "toolchain.json"
        config.write_text(json.dumps(self.toolchain))
        output = self.root / "public.json"
        neighbor = self.root / "public.json.tmp"
        neighbor.write_bytes(b"PRESERVE_EXISTING_FILE")
        result = self.cli(config, output)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(neighbor.read_bytes(), b"PRESERVE_EXISTING_FILE")


if __name__ == "__main__":
    unittest.main()
