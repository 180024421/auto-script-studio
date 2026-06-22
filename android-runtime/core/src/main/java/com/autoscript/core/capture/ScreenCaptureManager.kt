package com.autoscript.core.capture

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.util.DisplayMetrics
import android.util.Log
import android.view.WindowManager
import com.autoscript.core.model.ScreenFrame
import java.nio.ByteBuffer
import java.util.concurrent.atomic.AtomicReference

class ScreenCaptureManager(private val context: Context) {

    private var projection: MediaProjection? = null
    private var imageReader: ImageReader? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var width = 0
    private var height = 0
    private val reuseBuffer = AtomicReference<ByteArray?>(null)

    fun isActive(): Boolean = projection != null

    fun createCaptureIntent(): Intent {
        val mgr = context.getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        return mgr.createScreenCaptureIntent()
    }

    fun start(resultCode: Int, data: Intent) {
        stop()
        val mgr = context.getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        val proj = mgr.getMediaProjection(resultCode, data)
            ?: throw IllegalStateException("MediaProjection 获取失败")
        projection = proj

        val wm = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val metrics = DisplayMetrics()
        @Suppress("DEPRECATION")
        wm.defaultDisplay.getRealMetrics(metrics)
        width = metrics.widthPixels
        height = metrics.heightPixels

        val reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
        imageReader = reader
        virtualDisplay = proj.createVirtualDisplay(
            "AutoScriptCapture",
            width,
            height,
            metrics.densityDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            reader.surface,
            null,
            null,
        )
        Log.i(TAG, "Capture started ${width}x$height")
    }

    fun stop() {
        virtualDisplay?.release()
        virtualDisplay = null
        imageReader?.close()
        imageReader = null
        projection?.stop()
        projection = null
    }

    fun captureFrame(): ScreenFrame? {
        val reader = imageReader ?: return null
        val image = reader.acquireLatestImage() ?: return null
        try {
            val plane = image.planes[0]
            val buffer: ByteBuffer = plane.buffer
            val pixelStride = plane.pixelStride
            val rowStride = plane.rowStride
            val rowPadding = rowStride - pixelStride * width

            val bgrSize = width * height * 3
            var out = reuseBuffer.get()
            if (out == null || out.size != bgrSize) {
                out = ByteArray(bgrSize)
                reuseBuffer.set(out)
            }

            var o = 0
            val row = ByteArray(rowStride)
            buffer.rewind()
            for (y in 0 until height) {
                buffer.position(y * rowStride)
                val toRead = rowStride.coerceAtMost(buffer.remaining())
                buffer.get(row, 0, toRead)
                var xOffset = 0
                for (x in 0 until width) {
                    val i = xOffset
                    val r = row[i].toInt() and 0xFF
                    val g = row[i + 1].toInt() and 0xFF
                    val b = row[i + 2].toInt() and 0xFF
                    out[o++] = b.toByte()
                    out[o++] = g.toByte()
                    out[o++] = r.toByte()
                    xOffset += pixelStride
                }
                xOffset += rowPadding
            }
            return ScreenFrame(width, height, out.copyOf())
        } finally {
            image.close()
        }
    }

    companion object {
        private const val TAG = "AutoScriptCapture"

        const val REQUEST_MEDIA_PROJECTION = 9001

        fun handleActivityResult(
            manager: ScreenCaptureManager,
            resultCode: Int,
            data: Intent?,
        ): Boolean {
            if (resultCode != Activity.RESULT_OK || data == null) return false
            manager.start(resultCode, data)
            return true
        }
    }
}
