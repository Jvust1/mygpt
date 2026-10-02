import com.android.build.api.AndroidPluginVersion
import com.android.build.api.variant.ApplicationAndroidComponentsExtension
import com.android.build.api.variant.LibraryAndroidComponentsExtension
import java.util.Properties

plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.library) apply false
    alias(libs.plugins.jetbrains.kotlin.android) apply false
}

// CI-only integration override: upstream source/pin and default local builds stay
// unchanged. Hosted runners have stable r29, not upstream's older preview r29.
if (providers.gradleProperty("mygptNativeCi").orNull == "true") {
    val stableNdk = "29.0.14206865"
    require(providers.gradleProperty("mygptNativeNdk").orNull == stableNdk) {
        "Native CI requires its declared preinstalled NDK"
    }
    require(providers.gradleProperty("android.builder.sdkDownload").orNull == "false") {
        "Native CI forbids SDK downloads"
    }
    require(providers.gradleProperty("org.gradle.java.installations.auto-download").orNull == "false") {
        "Native CI forbids JDK downloads"
    }
    require(gradle.gradleVersion == "8.14.3") { "Unexpected Gradle version" }
    val observed = mutableMapOf<String, String>()
    val local = Properties().apply { rootProject.file("local.properties").inputStream().use { load(it) } }
    val sdk = file(local.getProperty("sdk.dir")).canonicalFile
    val cmake = file(local.getProperty("cmake.dir")).canonicalFile
    require(file("$sdk/ndk/$stableNdk/source.properties").isFile) { "Missing preinstalled NDK" }
    require(file("$cmake/bin/cmake").isFile) { "Missing preinstalled CMake" }
    subprojects {
        plugins.withId("com.android.library") {
            extensions.getByType<LibraryAndroidComponentsExtension>().finalizeDsl { dsl ->
                dsl.ndkVersion = stableNdk
                dsl.buildToolsVersion = "36.0.0"
                observed["$name.ndkVersion"] = dsl.ndkVersion.orEmpty()
                observed["$name.compileSdk"] = dsl.compileSdk.toString()
                observed["$name.buildToolsVersion"] = dsl.buildToolsVersion.orEmpty()
                observed["$name.minSdk"] = dsl.defaultConfig.minSdk.toString()
                if (name == "llama-lib") {
                    observed["$name.cmakeVersion"] = dsl.externalNativeBuild.cmake.version.orEmpty()
                    observed["$name.abis"] = dsl.defaultConfig.ndk.abiFilters.sorted().joinToString(",")
                }
            }
        }
        plugins.withId("com.android.application") {
            extensions.getByType<ApplicationAndroidComponentsExtension>().finalizeDsl { dsl ->
                dsl.ndkVersion = stableNdk
                dsl.buildToolsVersion = "36.0.0"
                observed["$name.ndkVersion"] = dsl.ndkVersion.orEmpty()
                observed["$name.compileSdk"] = dsl.compileSdk.toString()
                observed["$name.buildToolsVersion"] = dsl.buildToolsVersion.orEmpty()
                observed["$name.minSdk"] = dsl.defaultConfig.minSdk.toString()
                observed["$name.abis"] = dsl.defaultConfig.ndk.abiFilters.sorted().joinToString(",")
            }
        }
    }
    gradle.projectsEvaluated {
        require(subprojects.map { it.name }.sorted() == listOf("app", "bridge", "llama-lib")) {
            "Unexpected native CI modules"
        }
        subprojects.forEach { child ->
            val components = if (child.name == "app") {
                child.extensions.getByType<ApplicationAndroidComponentsExtension>()
            } else {
                child.extensions.getByType<LibraryAndroidComponentsExtension>()
            }
            observed["${child.name}.sdkDir"] = components.sdkComponents.sdkDirectory.get().asFile.canonicalPath
            val pluginVersion = components.pluginVersion
            require(pluginVersion == AndroidPluginVersion(8, 13, 2)) { "Unexpected Android Gradle plugin" }
            observed["${child.name}.agpVersion"] = "${pluginVersion.major}.${pluginVersion.minor}.${pluginVersion.micro}"
        }
        for (module in listOf("app", "bridge", "llama-lib")) {
            require(observed["$module.ndkVersion"] == stableNdk &&
                observed["$module.compileSdk"] == "36" &&
                observed["$module.minSdk"] == "33" &&
                observed["$module.buildToolsVersion"] == "36.0.0" &&
                observed["$module.sdkDir"] == sdk.path &&
                observed["$module.agpVersion"] == "8.13.2") { "Native CI DSL mismatch" }
        }
        require(observed["llama-lib.cmakeVersion"] == "3.31.6") { "Unexpected upstream CMake" }
        require(observed["llama-lib.abis"] == "arm64-v8a,x86_64" && observed["app.abis"] == "arm64-v8a") {
            "Unexpected upstream ABI scope"
        }
        observed["sourceCommit"] = providers.environmentVariable("GITHUB_SHA").get()
        observed["sdkDir"] = sdk.path
        observed["cmakeDir"] = cmake.path
        observed["gradleVersion"] = gradle.gradleVersion
        observed["javaHome"] = file(System.getProperty("java.home")).canonicalPath
        observed["sdkDownload"] = providers.gradleProperty("android.builder.sdkDownload").get()
        observed["javaDownload"] = providers.gradleProperty("org.gradle.java.installations.auto-download").get()
        observed["modules"] = "app,bridge,llama-lib"
        val report = layout.buildDirectory.file("native-ci-config.properties").get().asFile
        report.parentFile.mkdirs()
        report.writeText(observed.toSortedMap().entries.joinToString("\n", postfix = "\n") { "${it.key}=${it.value}" })
    }
}
