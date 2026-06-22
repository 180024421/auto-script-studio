package com.autoscript.vision.util

import android.graphics.Bitmap
import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame

object FrameUtils {

    fun toBitmap(frame: ScreenFrame, roi: Rect? = null): Bitmap {
        val r = roi?.clamp(frame.width, frame.height)
        val x = r?.x ?: 0
        val y = r?.y ?: 0
        val w = r?.w ?: frame.width
        val h = r?.h ?: frame.height
        val pixels = IntArray(w * h)
        var o = 0
        for (row in y until y + h) {
            for (col in x until x + w) {
                val j = (row * frame.width + col) * 3
                val b = frame.bgr[j].toInt() and 0xFF
                val g = frame.bgr[j + 1].toInt() and 0xFF
                val red = frame.bgr[j + 2].toInt() and 0xFF
                pixels[o++] = (0xFF shl 24) or (red shl 16) or (g shl 8) or b
            }
        }
        return Bitmap.createBitmap(pixels, w, h, Bitmap.Config.ARGB_8888)
    }

    fun bgrAt(frame: ScreenFrame, x: Int, y: Int): Triple<Int, Int, Int> = frame.bgrAt(x, y)
}
