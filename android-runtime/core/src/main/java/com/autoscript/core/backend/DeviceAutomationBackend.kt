package com.autoscript.core.backend

import com.autoscript.core.accessibility.AutomationAccessibilityService
import com.autoscript.core.capture.CaptureSession
import com.autoscript.core.log.ScriptLog
import com.autoscript.core.model.ScreenFrame
import com.autoscript.core.perf.PerfMonitor
import com.autoscript.core.project.ProjectConfig
import com.autoscript.core.root.RootInput
import com.autoscript.core.root.RootScreenCapture
import com.autoscript.core.root.RootShell
import com.autoscript.core.root.ShizukuInputBackend

/**
 * 统一自动化后端：输入（点击/滑动）与截屏可独立配置。
 * screenshot_mode 为 media_projection / accessibility 时，即使 auto/root 也不走 su screencap。
 */
class DeviceAutomationBackend(private val config: ProjectConfig) : AutomationBackend {

    private val mode: String = config.inputMode.lowercase()
    private val screenshotMode: String = config.screenshotMode.lowercase()
    private val useShizukuInput: Boolean
    private val useRootInput: Boolean
    private val useRootCapture: Boolean

    init {
        val rootOk = RootShell.isAvailable()
        val shizukuOk = mode == "shizuku" && ShizukuInputBackend.isReady()
        useShizukuInput = shizukuOk
        useRootInput = when (mode) {
            "shizuku" -> shizukuOk || rootOk
            "root" -> rootOk
            "accessibility" -> false
            else -> rootOk
        }
        useRootCapture = when (screenshotMode) {
            "media_projection", "accessibility" -> false
            else -> when (mode) {
                "root", "shizuku" -> rootOk
                "accessibility" -> false
                else -> rootOk
            }
        }
        val captureLabel = when {
            useRootCapture -> "root screencap"
            screenshotMode == "accessibility" -> "无障碍截图"
            else -> "MediaProjection"
        }
        val inputLabel = when {
            useShizukuInput -> "Shizuku"
            useRootInput -> "root input"
            else -> "无障碍手势"
        }
        ScriptLog.i("input_mode=$mode screenshot_mode=$screenshotMode → 点击:$inputLabel 截屏:$captureLabel")
    }

    override suspend fun capture(): ScreenFrame {
        val t0 = System.nanoTime()
        val frame = captureInternal()
        PerfMonitor.recordCapture((System.nanoTime() - t0) / 1_000_000)
        return frame
    }

    private suspend fun captureInternal(): ScreenFrame {
        if (useRootCapture) {
            val frame = RootScreenCapture.captureFrame()
            if (frame != null) return frame
            if (mode == "root" || screenshotMode == "root") {
                throw IllegalStateException("root 截屏失败，请确认 su 权限")
            }
        }
        return CaptureSession.captureFrame()
            ?: throw IllegalStateException("截屏失败，请授权录屏或开启无障碍截图")
    }

    override suspend fun tap(x: Int, y: Int) {
        if (useShizukuInput) {
            if (ShizukuInputBackend.tap(x, y)) return
        }
        if (useRootInput) {
            if (!RootInput.tap(x, y)) throw IllegalStateException("root 点击失败 ($x,$y)")
            return
        }
        val svc = requireA11y()
        if (!svc.tap(x, y)) throw IllegalStateException("点击失败 ($x,$y)")
    }

    override suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int) {
        if (useShizukuInput) {
            if (ShizukuInputBackend.swipe(x1, y1, x2, y2, durationMs)) return
        }
        if (useRootInput) {
            if (!RootInput.swipe(x1, y1, x2, y2, durationMs)) throw IllegalStateException("root 滑动失败")
            return
        }
        val svc = requireA11y()
        if (!svc.swipe(x1, y1, x2, y2, durationMs)) throw IllegalStateException("滑动失败")
    }

    override suspend fun longPress(x: Int, y: Int, durationMs: Int) {
        if (useShizukuInput) {
            if (ShizukuInputBackend.longPress(x, y, durationMs)) return
        }
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
        val inputOk = when {
            useShizukuInput -> ShizukuInputBackend.isReady()
            useRootInput -> RootShell.isAvailable()
            else -> AutomationAccessibilityService.isConnected()
        }
        return captureOk && inputOk
    }

    fun needsAccessibility(): Boolean =
        screenshotMode == "accessibility" || (!useRootInput && !useShizukuInput) || screenshotMode == "accessibility"
    fun needsMediaProjection(): Boolean = !useRootCapture && CaptureSession.needsMediaProjection()
    fun usingRoot(): Boolean = useRootInput || useRootCapture

    fun captureModeLabel(): String = when {
        useRootCapture -> "root"
        screenshotMode == "accessibility" -> "accessibility"
        else -> "projection"
    }

    fun inputModeLabel(): String = when {
        useShizukuInput -> "shizuku"
        useRootInput -> "root"
        else -> "accessibility"
    }

    private fun requireA11y(): AutomationAccessibilityService =
        AutomationAccessibilityService.get()
            ?: throw IllegalStateException("无障碍服务未开启")
}
