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
    }
}

rootProject.name = "MyGPTLlamaBridge"
include(":llama-lib")
project(":llama-lib").projectDir =
    file("../third_party/llama.cpp/upstream/examples/llama.android/lib")
include(":bridge")

include(":app")

include(":companion")
