package com.autoscript.vision.template

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import com.autoscript.core.model.ScreenFrame
import java.io.InputStream

object TemplateLoader {

    fun fromPngStream(input: InputStream): ScreenFrame {
        val bmp = BitmapFactory.decodeStream(input) ?: throw IllegalArgumentException("无法解码 PNG")
        return fromBitmap(bmp)
    }

    fun fromBitmap(bmp: Bitmap): ScreenFrame {
        val w = bmp.width
        val h = bmp.height
        val pixels = IntArray(w * h)
        bmp.getPixels(pixels, 0, w, 0, 0, w, h)
        val bgr = ByteArray(w * h * 3)
        var o = 0
        for (p in pixels) {
            bgr[o++] = (p and 0xFF).toByte()           // B
            bgr[o++] = ((p shr 8) and 0xFF).toByte()   // G
            bgr[o++] = ((p shr 16) and 0xFF).toByte()  // R
        }
        if (!bmp.isRecycled) bmp.recycle()
        return ScreenFrame(w, h, bgr)
    }
}
