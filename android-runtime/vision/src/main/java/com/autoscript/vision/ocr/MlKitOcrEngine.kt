package com.autoscript.vision.ocr

import android.content.Context
import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame
import com.autoscript.core.model.TextHit
import com.autoscript.vision.util.FrameUtils
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/**
 * 离线中文识字（ML Kit 捆绑模型）。
 */
class MlKitOcrEngine(appContext: Context) : OcrEngine {

    private val recognizer = TextRecognition.getClient(
        ChineseTextRecognizerOptions.Builder().build(),
    )
    private val context = appContext.applicationContext

    override fun recognize(frame: ScreenFrame, roi: Rect?, minConfidence: Float): List<TextHit> {
        val bitmap = FrameUtils.toBitmap(frame, roi)
        val image = InputImage.fromBitmap(bitmap, 0)
        val resultRef = AtomicReference<List<TextHit>>(emptyList())
        val errRef = AtomicReference<Exception?>(null)
        val latch = CountDownLatch(1)
        val offsetX = roi?.x ?: 0
        val offsetY = roi?.y ?: 0

        recognizer.process(image)
            .addOnSuccessListener { visionText ->
                val hits = mutableListOf<TextHit>()
                for (block in visionText.textBlocks) {
                    for (line in block.lines) {
                        val text = line.text.trim()
                        if (text.isEmpty()) continue
                        val box = line.boundingBox ?: continue
                        val conf = line.confidence ?: 0.85f
                        if (conf < minConfidence) continue
                        val rect = Rect(
                            box.left + offsetX,
                            box.top + offsetY,
                            box.width(),
                            box.height(),
                        )
                        hits.add(
                            TextHit(
                                text = text,
                                centerX = rect.x + rect.w / 2,
                                centerY = rect.y + rect.h / 2,
                                confidence = conf,
                                rect = rect,
                            ),
                        )
                    }
                }
                resultRef.set(hits)
                latch.countDown()
            }
            .addOnFailureListener { e ->
                errRef.set(e as? Exception ?: Exception(e))
                latch.countDown()
            }

        if (!latch.await(15, TimeUnit.SECONDS)) {
            throw IllegalStateException("识字超时")
        }
        errRef.get()?.let { throw it }
        if (!bitmap.isRecycled) bitmap.recycle()
        return resultRef.get()
    }

    override fun release() {
        recognizer.close()
    }
}
