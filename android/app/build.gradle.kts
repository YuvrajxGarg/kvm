plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// The app's version is the desktop's (../../VERSION), so a release ships all three together.
val kvmVersion = rootProject.file("../VERSION").readText().trim()
val parts = kvmVersion.split(".").map { it.toIntOrNull() ?: 0 } + listOf(0, 0, 0)

android {
    namespace = "pxl.kvm"
    compileSdk = 35

    defaultConfig {
        applicationId = "in.pxlvzn.kvm"
        minSdk = 29
        targetSdk = 35
        versionName = kvmVersion
        versionCode = parts[0] * 10000 + parts[1] * 100 + parts[2]
    }

    // Releases are signed with one fixed key, so each one installs over the last (Android refuses an
    // update signed with another key). The key never sits in the repository: CI writes it from the
    // ANDROID_KEYSTORE secret (base64) and passes its path and password here. Without it the APK
    // is signed with the build machine's debug key, which installs but can't update the last one.
    val ks = System.getenv("KVM_KEYSTORE")?.let { file(it) }?.takeIf { it.exists() }
    signingConfigs {
        if (ks != null) create("kvm") {
            storeFile = ks
            storePassword = System.getenv("KVM_KEYSTORE_PASSWORD")
            keyAlias = System.getenv("KVM_KEY_ALIAS") ?: "kvm"
            keyPassword = System.getenv("KVM_KEYSTORE_PASSWORD")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = if (ks != null) signingConfigs.getByName("kvm") else signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging {
        resources.excludes += setOf("META-INF/versions/9/OSGI-INF/MANIFEST.MF", "META-INF/DEPENDENCIES")
    }
    lint {
        abortOnError = false
        checkReleaseBuilds = false
    }
}

dependencies {
    implementation(project(":core"))
    implementation("org.bouncycastle:bcprov-jdk18on:1.78.1")
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
}
