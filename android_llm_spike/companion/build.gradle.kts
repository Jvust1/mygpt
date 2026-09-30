plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.jetbrains.kotlin.android)
}

val gdxVersion = "1.10.0"
val spineVersion = "4.1.0"
val natives by configurations.creating

android {
    namespace = "dev.mygpt.companionv2"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.mygpt.companionv2"
        minSdk = 33
        targetSdk = 36
        versionCode = 1
        versionName = "0.1-local-companion"
        ndk { abiFilters += "arm64-v8a" }
    }

    sourceSets.getByName("main").apply {
        java.srcDir("../../android_spike/src/main/java")
        java.srcDir("../../android_spike/app/src/main/java")
        java.srcDir("../../android_voice_spike/app/src/main/java")
        assets.srcDir("../../android_spike/app/src/main/assets")
        assets.srcDir("../../brain/personas")
        // Optional private build input. The Windows acceptance script populates
        // this build directory only after exact SHA-256 verification.
        assets.srcDir(layout.buildDirectory.dir("generated/bundled-skin-assets"))
        jniLibs.srcDir(layout.buildDirectory.dir("generated/gdx-jni"))
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin { jvmToolchain(17) }
}

dependencies {
    implementation(project(":bridge"))
    implementation(libs.androidx.core.ktx)
    implementation("com.github.k2-fsa.sherpa-onnx:sherpa-onnx:v1.13.8")
    implementation("org.apache.commons:commons-compress:1.28.0")
    implementation("com.esotericsoftware.spine:spine-libgdx:$spineVersion")
    implementation("com.badlogicgames.gdx:gdx:$gdxVersion")
    implementation("com.badlogicgames.gdx:gdx-backend-android:$gdxVersion")
    add("natives", "com.badlogicgames.gdx:gdx-platform:$gdxVersion:natives-arm64-v8a")
}

val copyGdxNatives by tasks.registering(Copy::class) {
    from(natives.map { zipTree(it) })
    include("**/*.so")
    eachFile { path = name }
    includeEmptyDirs = false
    into(layout.buildDirectory.dir("generated/gdx-jni/arm64-v8a"))
}

tasks.named("preBuild").configure { dependsOn(copyGdxNatives) }
