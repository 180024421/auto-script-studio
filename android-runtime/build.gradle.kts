plugins {
    id("com.android.application") version "8.2.2" apply false
    id("com.android.library") version "8.2.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.22" apply false
}

// 钉住 build-tools 33.0.1（app 与 library 两条分支必须同值）：不指定时 AGP 会按
// 当前 JDK 选最新的已安装版本，JDK21 环境下会挑到 36.x，产出的 DEX 版本 038
// 在 Android 7/8 设备上无法加载。compileSdk 仍是 34。
subprojects {
    plugins.withId("com.android.application") {
        extensions.configure<com.android.build.gradle.AppExtension> {
            buildToolsVersion = "33.0.1"
        }
    }
    plugins.withId("com.android.library") {
        extensions.configure<com.android.build.gradle.LibraryExtension> {
            buildToolsVersion = "33.0.1"
        }
    }
    tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
        kotlinOptions.jvmTarget = "17"
    }
}
