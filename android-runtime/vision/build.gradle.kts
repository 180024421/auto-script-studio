plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.autoscript.vision"
    compileSdk = 34

    defaultConfig {
        minSdk = 24
        targetSdk = 34
        consumerProguardFiles("consumer-rules.pro")
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
    implementation(project(":core"))
    implementation("androidx.core:core-ktx:1.12.0")
    // 中文识字（捆绑离线模型）
    implementation("com.google.mlkit:text-recognition-chinese:16.0.1")
    // YOLO ONNX 推理
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.17.3")
}
