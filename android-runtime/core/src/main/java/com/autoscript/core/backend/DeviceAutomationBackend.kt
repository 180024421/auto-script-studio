package com.autoscript.core.backend

import com.autoscript.core.accessibility.AutomationAccessibilityService
import com.autoscript.core.capture.ScreenCaptureManager
import com.autoscript.core.model.ScreenFrame

class DeviceAutomationBackend(
    private val capture: ScreenCaptureManager,
) : AutomationBackend {

    override suspend fun capture(): ScreenFrame {
        val frame = capture.captureFrame()
            ?: throw IllegalStateException("截屏失败，请确认已授权屏幕录制")
        return frame
    }

    override suspend fun tap(x: Int, y: Int) {
        val svc = requireA11y()
        if (!svc.tap(x, y)) throw IllegalStateException("点击失败 ($x,$y)")
    }

    override suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int) {
        val svc = requireA11y()
        if (!svc.swipe(x1, y1, x2, y2, durationMs)) throw IllegalStateException("滑动失败")
    }

    override suspend fun longPress(x: Int, y: Int, durationMs: Int) {
        val svc = requireA11y()
        if (!svc.longPress(x, y, durationMs)) throw IllegalStateException("长按失败")
    }

    override fun isReady(): Boolean =
        capture.isActive() && AutomationAccessibilityService.isConnected()

    private fun requireA11y(): AutomationAccessibilityService =
        AutomationAccessibilityService.get()
            ?: throw IllegalStateException("无障碍服务未开启")
}
