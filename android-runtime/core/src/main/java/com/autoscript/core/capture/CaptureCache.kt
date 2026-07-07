package com.autoscript.core.capture

import com.autoscript.core.model.ScreenFrame

/**
 * 同一轮查找循环内复用截屏帧，减少 capture 开销。
 */
class CaptureCache(private val ttlMs: Long = 80) {
    private var frame: ScreenFrame? = null
    private var capturedAt: Long = 0

    fun invalidate() {
        frame = null
        capturedAt = 0
    }

    suspend fun getOrCapture(capture: suspend () -> ScreenFrame): ScreenFrame {
        val now = System.currentTimeMillis()
        val cached = frame
        if (cached != null && now - capturedAt < ttlMs) {
            return cached
        }
        val fresh = capture()
        val stored = if (fresh.sharedBuffer) fresh.copy() else fresh
        frame = stored
        capturedAt = now
        return stored
    }
}
