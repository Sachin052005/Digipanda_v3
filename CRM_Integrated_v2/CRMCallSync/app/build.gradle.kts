plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.techpanda.callsync"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.techpanda.callsync"
        minSdk = 29          // Android 10
        targetSdk = 34   // 34 avoids Android 15 forcing content under the title bar
        versionCode = 3
        versionName = "1.2"
    }

    buildTypes {
        debug {
            // Debug builds may talk to http://<your-PC-IP>:8000 for testing.
            manifestPlaceholders["cleartext"] = "true"
        }
        release {
            isMinifyEnabled = false
            // Release builds (given to telecallers): HTTPS only.
            manifestPlaceholders["cleartext"] = "false"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.6")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
}
