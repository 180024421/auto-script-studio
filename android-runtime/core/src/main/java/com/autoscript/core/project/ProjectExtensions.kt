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
    val allowLocalImport: Boolean = true,
    val channel: String = "default",
)

data class ScheduleConfig(
    val enabled: Boolean = false,
    /** HH:mm，每日定时启动脚本 */
    val dailyTime: String = "",
)

/** project.json permissions：声明是否依赖无障碍/录屏等（为 false 时启动不强制授权）。 */
data class PermissionConfig(
    val accessibility: Boolean = true,
    val screenCapture: Boolean = true,
    val overlay: Boolean = true,
    val foregroundService: Boolean = true,
)

data class BootConfig(
    val autoStart: Boolean = false,
)

data class PerfConfig(
    val opencvMobile: Boolean = false,
    val yoloNnapi: Boolean = true,
    val yoloImgsz: Int = 320,
    val captureCacheTtlMs: Long = 80,
    /** 脚本启动时预热默认 YOLO 模型（加载 ONNX 会话） */
    val yoloWarmup: Boolean = true,
    /** seg 极速：限制掩码解码数量，配合 yoloMaxMaskDecode */
    val yoloSegFast: Boolean = false,
    /** 单次推理最多解码几个检测框的掩码质心（findYolo largest_mask 会适当放大） */
    val yoloMaxMaskDecode: Int = 50,
    /** onnx（默认）或 ncnn（导出 param/bin，运行时尚回退 ONNX） */
    val yoloBackend: String = "onnx",
)

data class DeviceProfile(
    val serial: String = "",
    val width: Int = 0,
    val height: Int = 0,
    val label: String = "default",
)
