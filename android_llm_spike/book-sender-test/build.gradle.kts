plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "dev.mygpt.bookcontexttest"
    compileSdk = 36

    defaultConfig {
        applicationId = "dev.mygpt.bookcontexttest"
        minSdk = 33
        targetSdk = 36
        versionCode = 1
        versionName = "0.1-book-context-test"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
