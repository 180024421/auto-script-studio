package com.autoscript.core.project

/**
 * project.json 中 license 段：对接 jiaoben /jiaoben/sercurity。
 */
data class LicenseConfig(
    val enabled: Boolean = false,
    val apiBase: String = "",
    val appName: String = "",
    val skipOnOffline: Boolean = false,
)

data class UpdateConfig(
    val enabled: Boolean = false,
    val manifestUrl: String = "",
    val checkOnStart: Boolean = true,
)

data class ScheduleConfig(
    val enabled: Boolean = false,
    /** HH:mm，每日定时启动脚本 */
    val dailyTime: String = "",
)

data class BootConfig(
    val autoStart: Boolean = false,
)

data class PerfConfig(
    val opencvMobile: Boolean = false,
    val yoloNnapi: Boolean = false,
)
