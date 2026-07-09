package com.autoscript.core.perf

/**
 * 最近一次视觉/截屏耗时（毫秒），供设置页展示与调优。
 */
object PerfMonitor {
    @Volatile var lastCaptureMs: Long = 0
        private set
    @Volatile var lastYoloMs: Long = 0
        private set
    @Volatile var lastYoloInferMs: Long = 0
        private set
    @Volatile var lastOcrMs: Long = 0
        private set
    @Volatile var captureCount: Long = 0
        private set
    @Volatile var yoloCount: Long = 0
        private set
    @Volatile var ocrCount: Long = 0
        private set

    fun recordCapture(ms: Long) {
        lastCaptureMs = ms
        captureCount++
    }

    fun recordYolo(ms: Long) {
        lastYoloMs = ms
        yoloCount++
    }

    fun recordYoloInfer(ms: Long) {
        lastYoloInferMs = ms
    }

    fun recordOcr(ms: Long) {
        lastOcrMs = ms
        ocrCount++
    }

    fun summary(): String = buildString {
        appendLine("截屏: ${lastCaptureMs}ms（累计 $captureCount 次）")
        appendLine("YOLO 总计: ${lastYoloMs}ms · 纯推理: ${lastYoloInferMs}ms（累计 $yoloCount 次）")
        append("OCR: ${lastOcrMs}ms（累计 $ocrCount 次）")
    }
}
