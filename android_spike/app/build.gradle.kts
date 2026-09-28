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
        versionCode = 1
        versionName = "0.0.1-spike"
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
