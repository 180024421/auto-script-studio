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

        val jiaobenApiBase = prop("jiaobenApiBase", "http://111.229.202.251:8687")
        val jiaobenProjectId = propInt("jiaobenProjectId", 0)
        buildConfigField("String", "JIAOBEN_API_BASE", "\"${jiaobenApiBase.replace("\"", "\\\"")}\"")
        buildConfigField("int", "JIAOBEN_PROJECT_ID", jiaobenProjectId.toString())

        ndk {
            abiFilters += listOf("arm64-v8a")
        }

        resValue("string", "app_name", prop("appName", "Auto Script"))
    }

    signingConfigs {
        val storeFilePath = packagerProps.getProperty("signingStoreFile")
        if (!storeFilePath.isNullOrBlank()) {
            create("release") {
                storeFile = file(storeFilePath)
                storePassword = packagerProps.getProperty("signingStorePassword", "")
                keyAlias = packagerProps.getProperty("signingKeyAlias", "")
                keyPassword = packagerProps.getProperty("signingKeyPassword", "")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            if (packagerProps.getProperty("signingStoreFile") != null) {
                signingConfig = signingConfigs.findByName("release")
            }
        }
        debug {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        buildConfig = true
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }

    sourceSets {
        getByName("main") {
            val generatedRes = rootProject.file("packager/generated-res")
            val defaultRes = rootProject.file("packager/default-res")
            val packedLauncher = generatedRes.resolve("mipmap-mdpi/ic_launcher.png")
            // 打包图标与默认 mipmap 只能二选一，避免 mergeDebugResources 重复资源
            res.srcDir(if (packedLauncher.exists()) generatedRes else defaultRes)
        }
    }
}

dependencies {
    implementation(project(":core"))
    implementation(project(":vision"))
    implementation(project(":script"))
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("androidx.activity:activity-ktx:1.8.2")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("dev.rikka.shizuku:api:13.1.5")
    implementation("dev.rikka.shizuku:provider:13.1.5")
}
