plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.jetbrains.kotlin.android)
}

android {
    namespace = "dev.mygpt.llmaspike"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.mygpt.llmaspike"
        minSdk = 33
        targetSdk = 36
        versionCode = 1
        versionName = "0.1-local-llama"
        ndk {
            abiFilters += "arm64-v8a"
        }
    }

    sourceSets.getByName("main").java.srcDir("../../android_spike/src/main/java")

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin {
        jvmToolchain(17)
    }
}

dependencies {
    implementation(project(":bridge"))
    implementation(libs.androidx.activity)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.core.ktx)
}
