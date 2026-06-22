import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val packagerProps = Properties().apply {
    val f = rootProject.file("packager/project.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

fun prop(key: String, default: String) = packagerProps.getProperty(key, default)
fun propInt(key: String, default: Int) = packagerProps.getProperty(key)?.toIntOrNull() ?: default

android {
    namespace = "com.autoscript.runtime"
    compileSdk = 34

    defaultConfig {
        applicationId = prop("applicationId", "com.autoscript.runtime")
        minSdk = 26
        targetSdk = 34
        versionCode = propInt("versionCode", 1)
        versionName = prop("versionName", "1.0.0")

        ndk {
            abiFilters += listOf("arm64-v8a")
        }

        resValue("string", "app_name", prop("appName", "Auto Script"))
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation(project(":core"))
    implementation(project(":vision"))
    implementation(project(":script"))
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
}
