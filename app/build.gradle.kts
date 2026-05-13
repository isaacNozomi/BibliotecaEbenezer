// app/build.gradle.kts
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("kotlin-kapt")        // Para Room y posible Dagger
}

android {
    namespace = "com.ebenezer.biblioteca"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.ebenezer.biblioteca"
        minSdk = 24          // Suficiente para FTS5 y Compose
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            // Permite instalar junto a la versión release si quieres
            applicationIdSuffix = ".debug"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"     // Robusto para corrutinas y lambdas
    }

    buildFeatures {
        compose = true       // ¡Obligatorio!
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.4"  // Estable con Kotlin 1.9.22
    }
}

dependencies {
    // --- Room (Base de datos local) ---
    val room_version = "2.6.1"
    implementation("androidx.room:room-runtime:$room_version")
    implementation("androidx.room:room-ktx:$room_version")       // Corrutinas
    kapt("androidx.room:room-compiler:$room_version")            // Procesador de anotaciones

    // --- Paging 3 (Carga por páginas para tu lista de párrafos) ---
    val paging_version = "3.2.1"
    implementation("androidx.paging:paging-runtime-ktx:$paging_version")
    implementation("androidx.paging:paging-compose:$paging_version") // Para LazyPagingItems

    // --- Vida útil y ViewModel (MVVM) ---
    val lifecycle_version = "2.7.0"
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:$lifecycle_version")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:$lifecycle_version")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:$lifecycle_version")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:$lifecycle_version")

    // --- Compose (Interfaz moderna) ---
    val compose_bom = platform("androidx.compose:compose-bom:2023.10.01")
    implementation(compose_bom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    // --- Núcleo de Android y Actividad ---
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.activity:activity-compose:1.8.2")

    // --- Debug (opcional pero útil para previsualizar) ---
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}