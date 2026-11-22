// Kvm for Android. `core` is plain Kotlin (the link, pairing and file protocol, tested on the JVM
// against numbers from the desktop's Python); `app` is the Android app around it.
// KVM_CORE_ONLY=1 builds and tests core without the Android SDK.
dependencyResolutionManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("androidx.*")
                includeGroupByRegex("com\\.google\\.android.*")
                includeGroupByRegex("com\\.google\\.testing.*")
            }
        }
        mavenCentral()
    }
}
rootProject.name = "kvm-android"
include(":core")
if (System.getenv("KVM_CORE_ONLY") == null) include(":app")
