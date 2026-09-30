plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.jetbrains.kotlin.android)
}

android {
    namespace = "dev.mygpt.llama"
    compileSdk = 36

    defaultConfig {
        minSdk = 33
        aarMetadata {
            minCompileSdk = 35
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin {
        jvmToolchain(17)
    }
}

dependencies {
    implementation(project(":llama-lib"))
    implementation(libs.androidx.core.ktx)
}
