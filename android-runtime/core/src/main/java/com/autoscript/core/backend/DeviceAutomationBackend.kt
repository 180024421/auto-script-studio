package com.autoscript.core.backend

import com.autoscript.core.accessibility.AutomationAccessibilityService
import com.autoscript.core.capture.CaptureSession
import com.autoscript.core.log.ScriptLog
import com.autoscript.core.model.ScreenFrame
import com.autoscript.core.project.ProjectConfig
import com.autoscript.core.root.RootInput
import com.autoscript.core.root.RootScreenCapture
import com.autoscript.core.root.RootShell

/**
 * 统一自动化后端：支持无障碍 / root / auto（优先 root）。
 */
class DeviceAutomationBackend(private val config: ProjectConfig) : AutomationBackend {

    private val mode: String = config.inputMode.lowercase()
    private val useRootInput: Boolean
    private val useRootCapture: Boolean

    init {
        val rootOk = RootShell.isAvailable()
        useRootInput = when (mode) {
            "root" -> rootOk
            "accessibility" -> false
            else -> rootOk // auto
        }
        useRootCapture = when (mode) {
            "root" -> rootOk
            "accessibility" -> false
            else -> rootOk
        }
        if (useRootInput || useRootCapture) {
            ScriptLog.i("input_mode=$mode → 使用 root（input=$useRootInput capture=$useRootCapture）")
        } else {
            ScriptLog.i("input_mode=$mode → 使用无障碍/录屏")
        }
    }

    override suspend fun capture(): ScreenFrame {
        if (useRootCapture) {
            val frame = RootScreenCapture.captureFrame()
            if (frame != null) return frame
            if (mode == "root") {
                throw IllegalStateException("root 截屏失败，请确认 su 权限")
            }
        }
        val frame = CaptureSession.captureFrame()
            ?: throw IllegalStateException("截屏失败，请授权录屏或开启无障碍截图")
        return frame
    }

    override suspend fun tap(x: Int, y: Int) {
        if (useRootInput) {
            if (!RootInput.tap(x, y)) throw IllegalStateException("root 点击失败 ($x,$y)")
            return
        }
        val svc = requireA11y()
        if (!svc.tap(x, y)) throw IllegalStateException("点击失败 ($x,$y)")
    }

    override suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int) {
        if (useRootInput) {
            if (!RootInput.swipe(x1, y1, x2, y2, durationMs)) throw IllegalStateException("root 滑动失败")
            return
        }
        val svc = requireA11y()
        if (!svc.swipe(x1, y1, x2, y2, durationMs)) throw IllegalStateException("滑动失败")
    }

    override suspend fun longPress(x: Int, y: Int, durationMs: Int) {
        if (useRootInput) {
            if (!RootInput.longPress(x, y, durationMs)) throw IllegalStateException("root 长按失败")
            return
        }
        val svc = requireA11y()
        if (!svc.longPress(x, y, durationMs)) throw IllegalStateException("长按失败")
    }

    override fun isReady(): Boolean {
        val captureOk = if (useRootCapture) {
            RootShell.isAvailable()
        } else {
            CaptureSession.isActive()
        }
        val inputOk = if (useRootInput) {
            RootShell.isAvailable()
        } else {
            AutomationAccessibilityService.isConnected()
        }
        return captureOk && inputOk
    }

    fun needsAccessibility(): Boolean = !useRootInput
    fun needsMediaProjection(): Boolean = !useRootCapture && CaptureSession.needsMediaProjection()
    fun usingRoot(): Boolean = useRootInput || useRootCapture

    private fun requireA11y(): AutomationAccessibilityService =
        AutomationAccessibilityService.get()
            ?: throw IllegalStateException("无障碍服务未开启")
}
