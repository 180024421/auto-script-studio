package com.autoscript.core.root

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import com.autoscript.core.capture.bitmapToScreenFrame
import com.autoscript.core.model.ScreenFrame
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

object RootScreenCapture {

    suspend fun captureFrame(): ScreenFrame? = withContext(Dispatchers.IO) {
        val png = RootShell.execOutput("screencap -p", timeoutSec = 8) ?: return@withContext null
        val bmp = BitmapFactory.decodeByteArray(png, 0, png.size) ?: return@withContext null
        bitmapToScreenFrame(bmp)
    }

    fun isAvailable(): Boolean = RootShell.isAvailable()
}
