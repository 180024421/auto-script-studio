package com.autoscript.core.capture

import android.os.Build
import com.autoscript.core.accessibility.AutomationAccessibilityService

/**
 * 统一截屏入口：MediaProjection 或无障碍 takeScreenshot（测试/模拟器免录屏授权）。
 */
object CaptureSession {
    @Volatile
    private var manager: ScreenCaptureManager? = null

    @Volatile
    var useA11yScreenshot: Boolean = false

    fun bind(manager: ScreenCaptureManager) {
        this.manager = manager
    }

    fun isA11yScreenshotAvailable(): Boolean =
        useA11yScreenshot && Build.VERSION.SDK_INT >= Build.VERSION_CODES.R

    fun isActive(): Boolean {
        if (isA11yScreenshotAvailable()) {
            return AutomationAccessibilityService.isConnected()
        }
        return manager?.isActive() == true
    }

    suspend fun captureFrame(): com.autoscript.core.model.ScreenFrame? {
        if (isA11yScreenshotAvailable()) {
            val svc = AutomationAccessibilityService.get() ?: return null
            return svc.captureFrameA11y()
        }
        return manager?.captureFrame()
    }

    /** 无障碍截图（API 30+）模式下无需 MediaProjection */
    fun needsMediaProjection(): Boolean = !isA11yScreenshotAvailable()
}

fun bitmapToScreenFrame(bitmap: android.graphics.Bitmap): com.autoscript.core.model.ScreenFrame {
    val w = bitmap.width
    val h = bitmap.height
    val pixels = IntArray(w * h)
    bitmap.getPixels(pixels, 0, w, 0, 0, w, h)
    val bgr = ByteArray(w * h * 3)
    var o = 0
    for (p in pixels) {
        bgr[o++] = (p and 0xFF).toByte()
        bgr[o++] = ((p shr 8) and 0xFF).toByte()
        bgr[o++] = ((p shr 16) and 0xFF).toByte()
    }
    if (!bitmap.isRecycled) bitmap.recycle()
    return com.autoscript.core.model.ScreenFrame(w, h, bgr)
}
