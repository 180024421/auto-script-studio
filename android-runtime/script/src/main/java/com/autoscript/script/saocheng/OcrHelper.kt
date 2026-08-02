package com.autoscript.script.saocheng

import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

class OcrHelper {
    private val recognizer = TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build())

    suspend fun recognizeRegion(bitmap: Bitmap, l: Int, t: Int, r: Int, b: Int, pad: Int = 2): String {
        val cl = (l - pad).coerceAtLeast(0)
        val ct = (t - pad).coerceAtLeast(0)
        val cr = (r + pad).coerceAtMost(bitmap.width)
        val cb = (b + pad).coerceAtMost(bitmap.height)
        if (cr <= cl || cb <= ct) return ""
        val crop = Bitmap.createBitmap(bitmap, cl, ct, cr - cl, cb - ct)
        return try {
            recognizeBitmap(crop)
        } finally {
            if (crop !== bitmap) crop.recycle()
        }
    }

    suspend fun recognizeBitmap(bitmap: Bitmap): String = suspendCancellableCoroutine { cont ->
        val image = InputImage.fromBitmap(bitmap, 0)
        recognizer.process(image)
            .addOnSuccessListener { result ->
                cont.resume(result.text?.trim().orEmpty())
            }
            .addOnFailureListener {
                cont.resume("")
            }
    }

    fun close() {
        recognizer.close()
    }
}
