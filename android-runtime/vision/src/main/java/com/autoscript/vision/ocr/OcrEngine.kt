package com.autoscript.vision.ocr

import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame
import com.autoscript.core.model.TextHit

/**
 * OCR 接口。后续接入 NCNN PP-OCR mobile 或 ML Kit。
 */
interface OcrEngine {
    fun recognize(frame: ScreenFrame, roi: Rect? = null, minConfidence: Float = 0.5f): List<TextHit>
    fun release()
}

class StubOcrEngine : OcrEngine {
    override fun recognize(frame: ScreenFrame, roi: Rect?, minConfidence: Float): List<TextHit> =
        emptyList()

    override fun release() = Unit
}

object TextMatch {
    fun filter(
        hits: List<TextHit>,
        target: String,
        mode: String = "contains",
    ): List<TextHit> = hits.filter { h ->
        when (mode.lowercase()) {
            "exact" -> h.text == target
            else -> h.text.contains(target)
        }
    }
}
