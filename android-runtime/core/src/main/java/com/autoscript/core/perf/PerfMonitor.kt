package com.autoscript.core.perf

/**
 * 视觉/截屏耗时统计：最近一次 + 滑动窗口平均，供设置页与运行日志调优。
 */
object PerfMonitor {
    private const val WINDOW = 20
    private const val LOG_EVERY_OPS = 20L

    @Volatile var onPeriodicLog: ((String) -> Unit)? = null

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

    private val captureAvg = RollingAverage(WINDOW)
    private val yoloAvg = RollingAverage(WINDOW)
    private val inferAvg = RollingAverage(WINDOW)

    fun recordCapture(ms: Long) {
        lastCaptureMs = ms
        captureCount++
        captureAvg.add(ms)
        maybePeriodicLog()
    }

    fun recordYolo(ms: Long) {
        lastYoloMs = ms
        yoloCount++
        yoloAvg.add(ms)
        maybePeriodicLog()
    }

    fun recordYoloInfer(ms: Long) {
        lastYoloInferMs = ms
        inferAvg.add(ms)
    }

    fun recordOcr(ms: Long) {
        lastOcrMs = ms
        ocrCount++
    }

    fun avgCaptureMs(): Long = captureAvg.average()

    fun avgYoloMs(): Long = yoloAvg.average()

    fun avgYoloInferMs(): Long = inferAvg.average()

    fun summary(): String = buildString {
        appendLine("截屏: ${lastCaptureMs}ms（近${captureAvg.sampleCount}次均 ${avgCaptureMs()}ms，累计 $captureCount 次）")
        appendLine(
            "YOLO 总计: ${lastYoloMs}ms · 纯推理: ${lastYoloInferMs}ms" +
                "（近${yoloAvg.sampleCount}次均 ${avgYoloMs()}ms / 推理 ${avgYoloInferMs()}ms，累计 $yoloCount 次）",
        )
        append("OCR: ${lastOcrMs}ms（累计 $ocrCount 次）")
    }

    fun periodicLine(): String =
        "perf 近${WINDOW}次均: 截屏=${avgCaptureMs()}ms YOLO=${avgYoloMs()}ms 推理=${avgYoloInferMs()}ms"

    private fun maybePeriodicLog() {
        val total = captureCount + yoloCount
        if (total > 0 && total % LOG_EVERY_OPS == 0L) {
            onPeriodicLog?.invoke(periodicLine())
        }
    }

    private class RollingAverage(private val capacity: Int) {
        private val buf = LongArray(capacity)
        private var count = 0
        private var idx = 0

        val sampleCount: Int get() = count

        @Synchronized
        fun add(value: Long) {
            buf[idx] = value
            idx = (idx + 1) % capacity
            if (count < capacity) count++
        }

        @Synchronized
        fun average(): Long {
            if (count == 0) return 0L
            var sum = 0L
            for (i in 0 until count) sum += buf[i]
            return sum / count
        }
    }
}
