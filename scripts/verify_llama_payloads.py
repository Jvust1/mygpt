"""Bounded structural verifier for the pinned llama Android build artifacts.

stdlib only; never loads native code, invokes Java, reads model/asset members, or
runs inference. Hashes identify whole packages; only classes.jar, DEX and ARM64
.so member bodies are inspected. Synthetic tests are not native build evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import sys
import tempfile
import zipfile
import zlib

UPSTREAM_COMMIT = "ba0ba54d93b25faf1e149f4ccedd3e9d84798563"
# Verified against examples/llama.android/lib/src/main/cpp/ai_chat.cpp at the pin.
JNI_EXPORTS = frozenset("Java_com_arm_aichat_internal_InferenceEngineImpl_" + method for method in (
    "init", "load", "prepare", "systemInfo", "benchModel", "processSystemPrompt",
    "processUserPrompt", "generateNextToken", "unload", "shutdown"))
JNI_CLASS = "com/arm/aichat/internal/InferenceEngineImpl"
JNI_METHODS = {
    "init": "(Ljava/lang/String;)V", "load": "(Ljava/lang/String;)I", "prepare": "()I",
    "systemInfo": "()Ljava/lang/String;", "benchModel": "(IIII)Ljava/lang/String;",
    "processSystemPrompt": "(Ljava/lang/String;)I", "processUserPrompt": "(Ljava/lang/String;I)I",
    "generateNextToken": "()Ljava/lang/String;", "unload": "()V", "shutdown": "()V",
}
LLAMA_CLASSES = frozenset(("com/arm/aichat/AiChat", "com/arm/aichat/InferenceEngine",
                          "com/arm/aichat/internal/InferenceEngineImpl"))
BRIDGE_CLASSES = frozenset(("dev/mygpt/llama/LlamaCppCompanionEngine",))
APK_CLASSES = LLAMA_CLASSES | BRIDGE_CLASSES | {"dev/mygpt/llmaspike/MainActivity"}
# The pinned Android CMake branch unconditionally builds these seven MODULE
# targets with GGML_BACKEND_DL/GGML_CPU_ALL_VARIANTS enabled. They are dlopen
# inputs, so DT_NEEDED closure alone cannot detect their absence.
# ggml/src/CMakeLists.txt lines 532-540 at UPSTREAM_COMMIT.
ARM64_BACKENDS = frozenset("libggml-cpu-android_" + variant + ".so" for variant in (
    "armv8.0_1", "armv8.2_1", "armv8.2_2", "armv8.6_1", "armv9.0_1", "armv9.2_1", "armv9.2_2"))
BACKEND_EXPORTS = frozenset(("ggml_backend_init", "ggml_backend_score"))
# Deliberately narrow public Android NDK libraries used by this CPU-only build.
# libc++_shared.so and libomp.so are NOT system libraries and must be packaged.
ANDROID_SYSTEM_LIBRARIES = frozenset(("libandroid.so", "liblog.so", "libc.so", "libm.so", "libdl.so"))
TOOLCHAIN_CONSTANTS = {
    "sdk": 36, "build_tools": "36.0.0", "ndk": "29.0.14206865",
    "upstream_ndk": "29.0.13113456", "cmake": "3.31.6", "ninja": "1.13.2",
    "gradle": "8.14.3", "gradle_distribution_sha256":
        "bd71102213493060956ec229d946beee57158dbd89d0e62b91bca0fa2c5f3531",
    "agp": "8.13.2", "kotlin": "2.3.0", "java_major": 17,
    "kleidiai_version": "1.24.0", "kleidiai_archive_md5": "2f02ebe29573d45813e671eb304f2a00",
    "ci_ndk_override": True, "existing_licenses_verified": True,
    "auto_sdk_download": False, "configured_toolchain_verified": True,
}
ERROR_CODES = frozenset(("INVALID_SOURCE", "INVALID_TOOLCHAIN", "INVALID_SUMMARY", "ARTIFACT_IO",
    "ZIP_INVALID", "ZIP_DUPLICATE", "ZIP_MEMBER_INVALID", "ZIP_LIMIT", "PAYLOAD_MISSING",
    "CLASS_INVALID", "CLASS_MISSING", "DEX_INVALID", "DEX_CLASS_MISSING", "ELF_INVALID",
    "ELF_ABI", "ELF_TYPE", "JNI_EXPORT_MISSING", "NATIVE_DEPENDENCY_MISSING",
    "NATIVE_DUPLICATE", "JNI_DECLARATION_MISSING", "BACKEND_MISSING", "BACKEND_EXPORT_MISSING", "CLI_INVALID"))
MAX_ARCHIVE = 1024 * 1024 * 1024
MAX_MEMBER = 512 * 1024 * 1024
MAX_SELECTED = 1024 * 1024 * 1024


class PayloadError(ValueError):
    """Only fixed public codes, never input paths, member names or contents."""
    def __init__(self, code):
        super().__init__(code if code in ERROR_CODES else "INVALID_SUMMARY")


def require(condition, code):
    if not condition:
        raise PayloadError(code)


def span(data, offset, size, code):
    require(type(offset) is int and type(size) is int and offset >= 0 and size >= 0
            and offset <= len(data) and size <= len(data) - offset, code)
    return data[offset:offset + size]


def unpack(fmt, data, offset, code):
    return struct.unpack(fmt, span(data, offset, struct.calcsize(fmt), code))


def validate_toolchain(value):
    require(type(value) is dict and set(value) == set(TOOLCHAIN_CONSTANTS) |
            {"java_version", "kleidiai_archive_sha256"},
            "INVALID_TOOLCHAIN")
    require(all(type(value[k]) is type(v) and value[k] == v for k, v in TOOLCHAIN_CONSTANTS.items()),
            "INVALID_TOOLCHAIN")
    require(type(value["java_version"]) is str and
            re.fullmatch(r"17(?:\.[0-9]+){1,3}", value["java_version"]) is not None, "INVALID_TOOLCHAIN")
    require(type(value["kleidiai_archive_sha256"]) is str and
            re.fullmatch(r"[0-9a-f]{64}", value["kleidiai_archive_sha256"]) is not None, "INVALID_TOOLCHAIN")
    return dict(value)


def _zip(raw):
    require(len(raw) <= MAX_ARCHIVE, "ZIP_LIMIT")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
        infos = archive.infolist()
        require(0 < len(infos) <= 100000, "ZIP_LIMIT")
        names = [entry.filename for entry in infos]
        require(len(names) == len(set(names)), "ZIP_DUPLICATE")
        for entry in infos:
            name = entry.filename
            require(entry.orig_filename == name and not name.startswith("/") and "\\" not in name
                    and all(part not in ("", ".", "..") for part in name.rstrip("/").split("/"))
                    and not any(ord(char) < 32 for char in name)
                    and not entry.flag_bits & 1 and (entry.external_attr >> 16) & 0o170000 != 0o120000,
                    "ZIP_MEMBER_INVALID")
            require(0 <= entry.header_offset < len(raw) and entry.file_size <= MAX_MEMBER,
                    "ZIP_LIMIT")
        return archive
    except (zipfile.BadZipFile, OSError, ValueError) as error:
        if isinstance(error, PayloadError):
            raise
        raise PayloadError("ZIP_INVALID") from None


def _read_member(archive, name):
    require(name in archive.namelist(), "PAYLOAD_MISSING")
    try:
        data = archive.read(name)  # zipfile checks the selected member's CRC.
        require(len(data) > 0, "PAYLOAD_MISSING")
        return data
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, zlib.error):
        raise PayloadError("ZIP_INVALID") from None


def _classfile(data, expected):
    """Validate the constant-pool identity and bounded classfile structure."""
    code = "CLASS_INVALID"
    require(span(data, 0, 4, code) == b"\xca\xfe\xba\xbe", code)
    minor, major, count = unpack(">HHH", data, 4, code)
    require(45 <= major <= 70 and count > 2, code)
    pool, offset, index = {}, 10, 1
    widths = {3: 4, 4: 4, 5: 8, 6: 8, 8: 2, 9: 4, 10: 4, 11: 4,
              12: 4, 15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}
    while index < count:
        tag = span(data, offset, 1, code)[0]
        offset += 1
        if tag == 1:
            size, = unpack(">H", data, offset, code)
            offset += 2
            pool[index] = (tag, span(data, offset, size, code))
            offset += size
        elif tag == 7:
            value, = unpack(">H", data, offset, code)
            pool[index] = (tag, value)
            offset += 2
        else:
            require(tag in widths, code)
            span(data, offset, widths[tag], code)
            offset += widths[tag]
            if tag in (5, 6):
                index += 1
                require(index < count, code)
        index += 1
    flags, this_class, superclass, interfaces = unpack(">HHHH", data, offset, code)
    offset += 8
    require(this_class in pool and pool[this_class][0] == 7, code)
    name_index = pool[this_class][1]
    require(pool.get(name_index) == (1, expected.encode("ascii")), code)
    span(data, offset, interfaces * 2, code)
    offset += interfaces * 2

    def attributes(at, number):
        for _ in range(number):
            name, length = unpack(">HI", data, at, code)
            require(name in pool and pool[name][0] == 1, code)
            at += 6
            span(data, at, length, code)
            at += length
        return at

    native_methods = {}
    for table in range(2):  # fields, methods
        number, = unpack(">H", data, offset, code)
        offset += 2
        for _ in range(number):
            access, name, descriptor, attrs = unpack(">HHHH", data, offset, code)
            require(name in pool and descriptor in pool and pool[name][0] == pool[descriptor][0] == 1, code)
            if table == 1 and access & 0x100 and not access & 0x8:
                native_methods[pool[name][1]] = pool[descriptor][1]
            offset = attributes(offset + 8, attrs)
    number, = unpack(">H", data, offset, code)
    require(attributes(offset + 2, number) == len(data), code)
    if expected == JNI_CLASS:
        require(all(native_methods.get(name.encode("ascii")) == signature.encode("ascii")
                    for name, signature in JNI_METHODS.items()), "JNI_DECLARATION_MISSING")


def _jar_classes(raw, expected):
    with _zip(raw) as jar:
        require(all(name + ".class" in jar.namelist() for name in expected), "CLASS_MISSING")
        for name in expected:
            _classfile(_read_member(jar, name + ".class"), name)
    return len(expected)


def _uleb(data, offset, code):
    value = 0
    for shift in range(0, 35, 7):
        byte = span(data, offset, 1, code)[0]
        offset += 1
        require(shift < 28 or byte <= 15, code)
        value |= (byte & 0x7f) << shift
        if not byte & 0x80:
            return value, offset
    raise PayloadError(code)


def _dex_classes(data):
    """Read real DEX class_defs -> type_ids -> string_ids, not substring hits."""
    code = "DEX_INVALID"
    require(len(data) >= 112 and data[:8] in {b"dex\n035\0", b"dex\n037\0", b"dex\n038\0",
                                         b"dex\n039\0", b"dex\n040\0"}, code)
    checksum, = unpack("<I", data, 8, code)
    require(checksum == zlib.adler32(data[12:]) & 0xffffffff
            and data[12:32] == hashlib.sha1(data[32:]).digest(), code)
    header = unpack("<20I", data, 32, code)
    (file_size, header_size, endian, link_size, link_off, map_off,
     strings_size, strings_off, types_size, types_off, protos_size, protos_off,
     fields_size, fields_off, methods_size, methods_off, classes_size, classes_off,
     data_size, data_off) = header
    require(file_size == len(data) and header_size == 112 and endian == 0x12345678
            and link_size == link_off == 0 and data_off >= 112 and data_off % 4 == 0
            and data_size == len(data) - data_off and data_off <= map_off < len(data), code)
    for size, offset, width in ((strings_size, strings_off, 4), (types_size, types_off, 4),
                                (protos_size, protos_off, 12), (fields_size, fields_off, 8),
                                (methods_size, methods_off, 8), (classes_size, classes_off, 32)):
        require((size == 0 and offset == 0) or (size > 0 and offset >= 112 and offset % 4 == 0
                and offset + size * width <= data_off), code)
    require(strings_size > 0 and types_size > 0 and classes_size > 0, code)
    map_size, = unpack("<I", data, map_off, code)
    require(0 < map_size <= 65536 and map_off % 4 == 0, code)
    map_types = {}
    for index in range(map_size):
        kind, unused, count, offset = unpack("<HHII", data, map_off + 4 + index * 12, code)
        require(kind not in map_types and unused == 0 and count > 0 and offset < len(data), code)
        map_types[kind] = (count, offset)
    require({0, 1, 2, 6, 0x1000, 0x2002} <= set(map_types), code)
    for kind, size, offset in ((0, 1, 0), (1, strings_size, strings_off), (2, types_size, types_off),
                               (3, protos_size, protos_off), (4, fields_size, fields_off),
                               (5, methods_size, methods_off), (6, classes_size, classes_off),
                               (0x1000, 1, map_off)):
        require((not size and kind not in map_types) or map_types.get(kind) == (size, offset), code)
    string_cache = {}

    def dex_string(index):
        require(index < strings_size, code)
        if index not in string_cache:
            offset, = unpack("<I", data, strings_off + index * 4, code)
            require(data_off <= offset < len(data), code)
            length, offset = _uleb(data, offset, code)
            end = data.find(b"\0", offset, min(len(data), offset + 1024 * 1024))
            require(end >= offset, code)
            raw = data[offset:end]
            if raw.isascii():
                require(length == len(raw), code)
            string_cache[index] = raw
        return string_cache[index]

    def type_descriptor(index):
        require(index < types_size, code)
        string_index, = unpack("<I", data, types_off + index * 4, code)
        return dex_string(string_index)

    def native_declarations(class_index, offset):
        require(data_off <= offset < len(data) and 0x2000 in map_types, "JNI_DECLARATION_MISSING")
        counts = []
        for _ in range(4):
            count, offset = _uleb(data, offset, code)
            counts.append(count)
        for count in counts[:2]:
            require(count <= fields_size, code)
            field = 0
            for _ in range(count):
                delta, offset = _uleb(data, offset, code)
                access, offset = _uleb(data, offset, code)
                field += delta
                require(field < fields_size, code)
        declarations = {}
        for count in counts[2:]:
            require(count <= methods_size, code)
            method = 0
            for _ in range(count):
                delta, offset = _uleb(data, offset, code)
                access, offset = _uleb(data, offset, code)
                code_off, offset = _uleb(data, offset, code)
                method += delta
                require(method < methods_size, code)
                owner, proto, name = unpack("<HHI", data, methods_off + method * 8, code)
                require(owner == class_index and proto < protos_size, code)
                if access & 0x100 and not access & 0x8:
                    require(code_off == 0, code)
                    shorty, return_type, parameters = unpack("<III", data, protos_off + proto * 12, code)
                    args = []
                    if parameters:
                        require(data_off <= parameters < len(data) and parameters % 4 == 0, code)
                        number, = unpack("<I", data, parameters, code)
                        require(number <= 65535, code)
                        for index in range(number):
                            parameter, = unpack("<H", data, parameters + 4 + index * 2, code)
                            args.append(type_descriptor(parameter))
                    method_name = dex_string(name)
                    require(method_name not in declarations, code)
                    declarations[method_name] = b"(" + b"".join(args) + b")" + type_descriptor(return_type)
        require(all(declarations.get(name.encode("ascii")) == signature.encode("ascii")
                    for name, signature in JNI_METHODS.items()), "JNI_DECLARATION_MISSING")
    result = set()
    class_indices = set()
    for index in range(classes_size):
        class_index, = unpack("<I", data, classes_off + index * 32, code)
        require(class_index < types_size and class_index not in class_indices, code)
        class_indices.add(class_index)
        descriptor = type_descriptor(class_index)
        require(descriptor.startswith(b"L") and descriptor.endswith(b";") and len(descriptor) > 2
                and descriptor not in result, code)
        result.add(descriptor)
        if descriptor == ("L" + JNI_CLASS + ";").encode("ascii"):
            class_data, = unpack("<I", data, classes_off + index * 32 + 24, code)
            native_declarations(class_index, class_data)
    return result


def _cstring(data, offset, code):
    require(0 <= offset < len(data), code)
    end = data.find(b"\0", offset)
    require(end >= offset, code)
    return data[offset:end]


def _elf(data):
    """Inspect bounded ELF64 LE ARM64 shared-library dynamic metadata.

    NDK strip retains section headers, .dynsym/.dynstr and .dynamic. Sectionless
    objects fail closed. Defined exports must point inside executable mapped
    section bytes; undefined/local/hidden/object symbols cannot satisfy JNI.
    """
    code = "ELF_INVALID"
    require(len(data) >= 64 and data[:4] == b"\x7fELF", code)
    require(data[4] == 2 and data[5] == 1, "ELF_ABI")
    require(data[6] == 1, code)
    (kind, machine, version, entry, phoff, shoff, flags, ehsize, phentsize,
     phnum, shentsize, shnum, shstrndx) = unpack("<HHIQQQIHHHHHH", data, 16, code)
    require(kind == 3, "ELF_TYPE")
    require(machine == 183, "ELF_ABI")
    require(version == 1 and ehsize == 64 and phentsize == 56 and shentsize == 64
            and 0 < phnum < 65535 and 0 < shnum < 65535 and 0 < shstrndx < shnum
            and phoff >= 64 and shoff >= 64, code)
    span(data, phoff, phnum * phentsize, code)
    span(data, shoff, shnum * shentsize, code)
    loads, dynamic_segments = [], []
    for index in range(phnum):
        ptype, pflags, offset, address, physical, filesz, memsz, align = unpack(
            "<IIQQQQQQ", data, phoff + index * 56, code)
        span(data, offset, filesz, code)
        if ptype == 1:
            require(filesz <= memsz and (align in (0, 1) or
                    (align & (align - 1) == 0 and offset % align == address % align)), code)
            loads.append((offset, address, filesz, pflags))
        elif ptype == 2:
            dynamic_segments.append((offset, address, filesz))
    require(loads and len(dynamic_segments) == 1, code)
    sections = []
    for index in range(shnum):
        section = unpack("<IIQQQQIIQQ", data, shoff + index * 64, code)
        name, stype, sflags, address, offset, size, link, info, align, entsize = section
        if stype != 8:  # SHT_NOBITS has no file body.
            span(data, offset, size, code)
        require(align in (0, 1) or align & (align - 1) == 0, code)
        sections.append(section)
    require(sections[0] == (0,) * 10 and sections[shstrndx][1] == 3, code)

    def mapped(section, executable=False):
        _, stype, sflags, address, offset, size, *_ = section
        return stype != 8 and size > 0 and sflags & 2 and (not executable or sflags & 4) and any(
            offset >= start and offset + size <= start + extent and address == base + offset - start
            and (not executable or pflags & 1) for start, base, extent, pflags in loads)

    dynsyms = [s for s in sections if s[1] == 11]
    dynamics = [s for s in sections if s[1] == 6]
    require(len(dynsyms) == len(dynamics) == 1, code)
    symbols, dynamic = dynsyms[0], dynamics[0]
    require(mapped(symbols) and mapped(dynamic) and symbols[9] == 24
            and symbols[5] >= 24 and symbols[5] % 24 == 0 and dynamic[9] == 16
            and dynamic[5] >= 16 and dynamic[5] % 16 == 0
            and 0 < symbols[6] < shnum and dynamic[6] == symbols[6], code)
    strings = sections[symbols[6]]
    require(strings[1] == 3 and mapped(strings), code)
    string_data = span(data, strings[4], strings[5], code)
    require(string_data[:1] == b"\0", code)
    dynamic_offset, dynamic_address, dynamic_size = dynamic_segments[0]
    require(dynamic[4] == dynamic_offset and dynamic[3] == dynamic_address
            and dynamic[5] <= dynamic_size, code)
    tags, needed, terminated = {}, set(), False
    for offset in range(dynamic[4], dynamic[4] + dynamic[5], 16):
        tag, value = unpack("<qQ", data, offset, code)
        if tag == 0:
            terminated = True
            break
        if tag == 1:
            name = _cstring(string_data, value, code)
            require(re.fullmatch(rb"lib[A-Za-z0-9_.+\-]+\.so", name) is not None, code)
            needed.add(name.decode("ascii"))
        elif tag in (5, 6, 10, 11):
            require(tag not in tags, code)
            tags[tag] = value
    require(terminated and tags == {5: strings[3], 6: symbols[3], 10: strings[5], 11: 24}, code)
    exports = set()
    for offset in range(symbols[4], symbols[4] + symbols[5], 24):
        name, info, other, index, value, size = unpack("<IBBHQQ", data, offset, code)
        symbol = _cstring(string_data, name, code)
        if index != 0 and info >> 4 in (1, 2) and info & 15 == 2 and other & 3 in (0, 3):
            require(index < shnum, code)
            section = sections[index]
            if mapped(section, executable=True) and size > 0 and section[3] <= value and \
                    value + size <= section[3] + section[5]:
                if symbol.isascii():
                    exports.add(symbol.decode("ascii"))
    return needed, exports


def _native(archive, prefix, required):
    names = [name for name in archive.namelist() if name.startswith(prefix) and name.endswith(".so")]
    require(not required or prefix + "libai-chat.so" in names, "PAYLOAD_MISSING")
    require(not required or {prefix + name for name in ARM64_BACKENDS} <= set(names), "BACKEND_MISSING")
    require(sum(archive.getinfo(name).file_size for name in names) <= MAX_SELECTED, "ZIP_LIMIT")
    libraries = {}
    export_count = 0
    for name in names:
        basename = name[len(prefix):]
        require("/" not in basename and re.fullmatch(r"lib[A-Za-z0-9_.+\-]+\.so", basename) is not None,
                "ZIP_MEMBER_INVALID")
        require(basename not in libraries, "NATIVE_DUPLICATE")
        needed, exports = _elf(_read_member(archive, name))
        libraries[basename] = needed
        if basename == "libai-chat.so":
            require(JNI_EXPORTS <= exports, "JNI_EXPORT_MISSING")
            export_count = len(JNI_EXPORTS)
        if basename in ARM64_BACKENDS:
            require(BACKEND_EXPORTS <= exports, "BACKEND_EXPORT_MISSING")
    require(all(dependency in libraries or dependency in ANDROID_SYSTEM_LIBRARIES
                for dependencies in libraries.values() for dependency in dependencies),
            "NATIVE_DEPENDENCY_MISSING")
    return len(libraries), sum(map(len, libraries.values())), export_count


def _artifact(path, kind):
    try:
        path = Path(path)
        require(path.is_file() and not path.is_symlink(), "ARTIFACT_IO")
        require(0 < path.stat().st_size <= MAX_ARCHIVE, "ZIP_LIMIT")
        raw = path.read_bytes()
    except (OSError, TypeError, ValueError) as error:
        if isinstance(error, PayloadError):
            raise
        raise PayloadError("ARTIFACT_IO") from None
    with _zip(raw) as archive:
        dex_files = 0
        if kind == "local_apk":
            names = [name for name in archive.namelist() if re.fullmatch(r"classes(?:[2-9]|[1-9][0-9]+)?\.dex", name)]
            require("classes.dex" in names, "PAYLOAD_MISSING")
            require(sum(archive.getinfo(name).file_size for name in names) <= MAX_SELECTED, "ZIP_LIMIT")
            classes = set()
            for name in names:
                found = _dex_classes(_read_member(archive, name))
                require(not classes & found, "DEX_INVALID")
                classes.update(found)
            require({("L" + name + ";").encode("ascii") for name in APK_CLASSES} <= classes,
                    "DEX_CLASS_MISSING")
            class_count, dex_files = len(APK_CLASSES), len(names)
            native = _native(archive, "lib/arm64-v8a/", True)
        else:
            expected = LLAMA_CLASSES if kind == "llama_aar" else BRIDGE_CLASSES
            class_count = _jar_classes(_read_member(archive, "classes.jar"), expected)
            native = _native(archive, "jni/arm64-v8a/", kind == "llama_aar")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "required_classes": class_count, "dex_files": dex_files, "arm64_libraries": native[0],
            "needed_edges": native[1], "required_jni_exports": native[2]}


SUMMARY_CONSTANTS = {"schema": "mygpt.llama-native-artifacts.v1", "status": "PASS",
    "scope": "ARM64_COMPILE_LINK_PACKAGE_ONLY", "upstream_commit": UPSTREAM_COMMIT,
    "inference_executed": False, "physical_device_accepted": False,
    "contains_binary_payloads": False, "contains_raw_logs": False}
ARTIFACT_KEYS = {"sha256", "bytes", "required_classes", "dex_files", "arm64_libraries",
                 "needed_edges", "required_jni_exports"}


def validate_summary(summary):
    require(type(summary) is dict and set(summary) == set(SUMMARY_CONSTANTS) |
            {"source_commit", "toolchain", "artifacts"}, "INVALID_SUMMARY")
    require(all(type(summary[k]) is type(v) and summary[k] == v for k, v in SUMMARY_CONSTANTS.items()),
            "INVALID_SUMMARY")
    require(type(summary["source_commit"]) is str and
            re.fullmatch(r"[0-9a-f]{40}", summary["source_commit"]) is not None, "INVALID_SOURCE")
    validate_toolchain(summary["toolchain"])
    artifacts = summary["artifacts"]
    require(type(artifacts) is dict and set(artifacts) == {"llama_aar", "bridge_aar", "local_apk"},
            "INVALID_SUMMARY")
    for name, artifact in artifacts.items():
        require(type(artifact) is dict and set(artifact) == ARTIFACT_KEYS, "INVALID_SUMMARY")
        require(type(artifact["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"])
                is not None and type(artifact["bytes"]) is int and 0 < artifact["bytes"] <= MAX_ARCHIVE,
                "INVALID_SUMMARY")
        require(all(type(artifact[k]) is int and 0 <= artifact[k] <= 1000000
                    for k in ARTIFACT_KEYS - {"sha256", "bytes"}), "INVALID_SUMMARY")
        require(artifact["required_classes"] == {"llama_aar": 3, "bridge_aar": 1, "local_apk": 5}[name],
                "INVALID_SUMMARY")
        require((artifact["dex_files"] > 0) == (name == "local_apk"), "INVALID_SUMMARY")
        if name != "bridge_aar":
            require(artifact["arm64_libraries"] >= 1 + len(ARM64_BACKENDS)
                    and artifact["required_jni_exports"] == len(JNI_EXPORTS),
                    "INVALID_SUMMARY")
        else:
            require(artifact["required_jni_exports"] in (0, len(JNI_EXPORTS)), "INVALID_SUMMARY")
    return summary


def inspect_artifacts(llama_aar, bridge_aar, local_apk, source_commit, toolchain):
    require(type(source_commit) is str and re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None,
            "INVALID_SOURCE")
    toolchain = validate_toolchain(toolchain)
    try:
        artifacts = {name: _artifact(path, name) for name, path in (
            ("llama_aar", llama_aar), ("bridge_aar", bridge_aar), ("local_apk", local_apk))}
    except PayloadError:
        raise
    except (OSError, EOFError, ValueError, TypeError, struct.error, zipfile.BadZipFile, zlib.error):
        raise PayloadError("ARTIFACT_IO") from None
    return validate_summary({**SUMMARY_CONSTANTS, "source_commit": source_commit,
                             "toolchain": toolchain, "artifacts": artifacts})


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise PayloadError("CLI_INVALID")


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "INVALID_TOOLCHAIN")
        result[key] = value
    return result


def main(argv=None):
    output = None
    temporary = None
    try:
        parser = _Parser(description=__doc__)
        for option in ("llama-aar", "bridge-aar", "apk", "source-commit", "toolchain-json", "output"):
            parser.add_argument("--" + option, required=True)
        args = parser.parse_args(argv)
        candidate = Path(args.output)
        require(candidate.resolve() not in {Path(value).resolve() for value in
                (args.llama_aar, args.bridge_aar, args.apk, args.toolchain_json)}, "CLI_INVALID")
        output = candidate
        # A failed rerun must not leave an earlier PASS available for upload.
        output.unlink(missing_ok=True)
        toolchain_path = Path(args.toolchain_json)
        require(toolchain_path.stat().st_size <= 8192, "INVALID_TOOLCHAIN")
        toolchain = json.loads(toolchain_path.read_text(encoding="utf-8"), object_pairs_hook=_json_object)
        summary = inspect_artifacts(args.llama_aar, args.bridge_aar, args.apk, args.source_commit, toolchain)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=".llama-summary-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(summary, sort_keys=True, indent=2) + "\n")
        temporary.replace(output)
        print(json.dumps({"status": "PASS"}))
        return 0
    except Exception as error:
        for path in (output, temporary):
            if path is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
        code = str(error) if isinstance(error, PayloadError) else "ARTIFACT_IO"
        print(json.dumps({"status": "FAIL", "error": code}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
