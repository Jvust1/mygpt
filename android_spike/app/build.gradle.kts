plugins {
    id("com.android.application")
}

val gdxVersion = "1.10.0"
val spineVersion = "4.1.0"
val natives by configurations.creating

android {
    namespace = "dev.mygpt.spike"
    compileSdk = 35

    defaultConfig {
        applicationId = "dev.mygpt.spike"
        minSdk = 24
        targetSdk = 35
        versionCode = 5
        versionName = "0.0.5-companion-ui-3714430278"
        ndk {
            // First device target is Xiaomi 14 / Snapdragon 8 Gen 3.
            abiFilters += "arm64-v8a"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    sourceSets.getByName("main").apply {
        java.srcDir("../src/main/java")
        jniLibs.srcDir(layout.buildDirectory.dir("generated/gdx-jni"))
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
}

dependencies {
    // 3714430278/skeleton.bin identifies itself as Spine 4.1.20.
    // Spine documents that runtimes match the exported major.minor line, so use 4.1.0.
    // Distribution remains license-gated; the exact runtime notice is bundled in assets.
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

tasks.named("preBuild").configure {
    dependsOn(copyGdxNatives)
}
