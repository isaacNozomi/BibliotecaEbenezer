// Archivo settings.gradle.kts
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
    // Aseguramos que los plugins se resuelvan con las versiones del archivo raíz
    resolutionStrategy {
        eachPlugin {
            if (requested.id.namespace == "com.android") {
                useModule("com.android.tools.build:gradle:8.2.0")
            }
            if (requested.id.namespace == "org.jetbrains.kotlin") {
                useVersion("1.9.22")
            }
        }
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "BibliotecaEbenezer"
include(":app")