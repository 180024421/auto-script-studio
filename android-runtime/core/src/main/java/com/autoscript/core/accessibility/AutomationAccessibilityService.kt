package com.autoscript.core.accessibility

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Bitmap
import android.graphics.Path
import android.os.Build
import android.util.Log
import android.view.Display
import android.view.accessibility.AccessibilityEvent
import com.autoscript.core.capture.bitmapToScreenFrame
import com.autoscript.core.log.ScriptLog
import com.autoscript.core.model.ScreenFrame
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.withTimeout
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicReference

class AutomationAccessibilityService : AccessibilityService() {

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance.set(this)
        Log.i(TAG, "Accessibility service connected")
        ScriptLog.i("无障碍服务已连接")
    }

    override fun onDestroy() {
        instance.set(null)
        super.onDestroy()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onInterrupt() = Unit

    suspend fun captureFrameA11y(): ScreenFrame? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return null
        val done = CompletableDeferred<Bitmap?>()
        val executor = Executors.newSingleThreadExecutor()
        takeScreenshot(
            Display.DEFAULT_DISPLAY,
            executor,
            object : TakeScreenshotCallback {
                override fun onSuccess(result: ScreenshotResult) {
                    val hw = Bitmap.wrapHardwareBuffer(result.hardwareBuffer, result.colorSpace)
                    val soft = hw?.copy(Bitmap.Config.ARGB_8888, false)
                    hw?.recycle()
                    done.complete(soft)
                }

                override fun onFailure(errorCode: Int) {
                    Log.w(TAG, "takeScreenshot failed: $errorCode")
                    done.complete(null)
                }
            },
        )
        return try {
            withTimeout(8_000) { done.await() }?.let { bitmapToScreenFrame(it) }
        } catch (e: Exception) {
            Log.e(TAG, "captureFrameA11y", e)
            null
        } finally {
            executor.shutdown()
        }
    }

    suspend fun tap(x: Int, y: Int): Boolean = dispatchTap(x, y, 50)

    suspend fun longPress(x: Int, y: Int, durationMs: Int): Boolean =
        dispatchTap(x, y, durationMs.coerceAtLeast(100))

    suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int): Boolean {
        val path = Path().apply {
            moveTo(x1.toFloat(), y1.toFloat())
            lineTo(x2.toFloat(), y2.toFloat())
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs.toLong())
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        return dispatchGestureAwait(gesture)
    }

    private suspend fun dispatchTap(x: Int, y: Int, durationMs: Int): Boolean {
        val path = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs.toLong())
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        return dispatchGestureAwait(gesture)
    }

    private suspend fun dispatchGestureAwait(gesture: GestureDescription): Boolean {
        val done = CompletableDeferred<Boolean>()
        val ok = dispatchGesture(
            gesture,
            object : GestureResultCallback() {
                override fun onCompleted(gestureDescription: GestureDescription?) {
                    done.complete(true)
                }

                override fun onCancelled(gestureDescription: GestureDescription?) {
                    done.complete(false)
                }
            },
            null,
        )
        if (!ok) return false
        return try {
            withTimeout(5_000) { done.await() }
        } catch (_: Exception) {
            false
        }
    }

    companion object {
        private const val TAG = "AutoScriptA11y"
        private val instance = AtomicReference<AutomationAccessibilityService?>()

        fun get(): AutomationAccessibilityService? = instance.get()

        fun isConnected(): Boolean = instance.get() != null
    }
}
