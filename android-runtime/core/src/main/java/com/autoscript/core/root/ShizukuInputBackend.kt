package com.autoscript.core.root

import com.autoscript.core.log.ScriptLog

/**
 * Shizuku 触控骨架：检测 Shizuku 是否可用，实际注入待集成 Shizuku API。
 * input_mode=shizuku 时由 [com.autoscript.core.backend.DeviceAutomationBackend] 选用。
 */
object ShizukuInputBackend {
    fun isAvailable(): Boolean {
        return try {
            val cls = Class.forName("rikka.shizuku.Shizuku")
            val method = cls.getMethod("pingBinder")
            method.invoke(null) as Boolean
        } catch (_: Exception) {
            false
        }
    }

    fun tap(x: Int, y: Int): Boolean {
        if (!isAvailable()) return false
        ScriptLog.i("Shizuku tap($x,$y) — 骨架实现，请集成 Shizuku UserService")
        return RootInput.tap(x, y)
    }

    fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int): Boolean {
        if (!isAvailable()) return false
        return RootInput.swipe(x1, y1, x2, y2, durationMs)
    }

    fun longPress(x: Int, y: Int, durationMs: Int): Boolean {
        if (!isAvailable()) return false
        return RootInput.longPress(x, y, durationMs)
    }
}
