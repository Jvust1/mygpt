pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://jitpack.io") }
    }
}

rootProject.name = "MyGPTLlamaBridge"
include(":llama-lib")
project(":llama-lib").projectDir =
    file("../third_party/llama.cpp/upstream/examples/llama.android/lib")
include(":bridge")

include(":app")

// Explicit opt-in: the build-only CI gate does not configure Companion/Spine,
// voice, Book sender/SDK or private visual inputs. Normal builds are unchanged.
val nativeCi = providers.gradleProperty("mygptNativeCi").orNull
require(nativeCi == null || nativeCi == "true") { "Invalid native CI mode" }
if (nativeCi != "true") {
    include(":companion")
    include(":book-sender-test")
    include(":book-client-sdk")
}
