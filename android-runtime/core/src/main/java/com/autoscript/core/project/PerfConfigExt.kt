package com.autoscript.core.project

/** project.json runtime.perf 可读摘要（设置页展示）。 */
fun PerfConfig.summaryLines(): List<String> = buildList {
    add("YOLO ${yoloImgsz}px · NNAPI ${if (yoloNnapi) "开" else "关"} · 后端 $yoloBackend")
    add("截屏缓存 ${captureCacheTtlMs}ms · 预热 ${if (yoloWarmup) "开" else "关"}")
    if (yoloSegFast) {
        add("seg 极速 · 最多解码 $yoloMaxMaskDecode 个掩码")
    }
    if (opencvMobile) add("OpenCV Mobile 大模板加速：开")
}

fun ProjectConfig.runtimePerfSummary(): String = buildString {
    appendLine("点击: ${inputMode} · 截屏: ${screenshotMode}")
    appendLine("循环间隔: ${defaultIntervalMs}ms · OCR: $ocrMode")
    perf.summaryLines().forEach { appendLine(it) }
}.trimEnd()
