plugins {
    id("com.android.application")
}

android {
    namespace = "dev.mygpt.spike"
    compileSdk = 35

    defaultConfig {
        applicationId = "dev.mygpt.spike"
        minSdk = 24
        targetSdk = 35
        versionCode = 2
        versionName = "0.0.2-spine-eval"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    sourceSets.getByName("main").java.srcDir("../src/main/java")

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
}

dependencies {
    // Spine binary is 4.1.20, so keep the runtime on the matching 4.1 line.
    // This debug spike is evaluation-only until Spine Runtime licensing is cleared for distribution.
    implementation("com.esotericsoftware.spine:spine-libgdx:4.1.0")
    implementation("com.badlogicgames.gdx:gdx:1.11.0")
    implementation("com.badlogicgames.gdx:gdx-backend-android:1.11.0")
}
