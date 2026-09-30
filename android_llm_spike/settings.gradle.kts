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

include(":companion")

include(":book-sender-test")
