plugins {
    id("com.android.application")
}

android {
    namespace = "dev.mygpt.voicespike"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.mygpt.voicespike"
        minSdk = 28
        targetSdk = 36
        versionCode = 1
        versionName = "0.1-sherpa-streaming"
        ndk { abiFilters += "arm64-v8a" }
    }

    sourceSets.getByName("main").java.srcDir("../../android_spike/src/main/java")

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    // Shared ACT parser uses strict Gson streaming only, without POJO reflection.
    implementation("com.google.code.gson:gson:2.14.0")
    implementation("com.github.k2-fsa.sherpa-onnx:sherpa-onnx:v1.13.8")
    implementation("org.apache.commons:commons-compress:1.28.0")
}
