package com.autoscript.vision

import com.autoscript.core.model.Detection
import com.autoscript.core.model.MatchResult
import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame
import com.autoscript.core.model.TextHit
import com.autoscript.core.project.ProjectAssets
import com.autoscript.vision.color.ColorFinder
import com.autoscript.vision.ocr.OcrEngine
import com.autoscript.vision.ocr.StubOcrEngine
import com.autoscript.vision.ocr.TextMatch
import com.autoscript.vision.template.TemplateLoader
import com.autoscript.vision.template.TemplateMatcher
import com.autoscript.vision.yolo.StubYoloDetector
import com.autoscript.vision.yolo.YoloDetector
import com.autoscript.vision.yolo.YoloPick
import java.io.ByteArrayInputStream

class VisionEngine(
    private val assets: ProjectAssets,
    ocrMode: String = "lazy",
) {
    private val templateCache = mutableMapOf<String, ScreenFrame>()
    private val yolo: YoloDetector = StubYoloDetector()
    private var ocr: OcrEngine? = if (ocrMode == "eager") StubOcrEngine() else null
    private val ocrMode = ocrMode

    fun findColor(frame: ScreenFrame, bgr: Triple<Int, Int, Int>, tol: Int, roi: Rect?): Pair<Int, Int>? =
        ColorFinder.findColor(frame, bgr, tol, roi)

    fun findTemplate(frame: ScreenFrame, path: String, threshold: Float, roi: Rect?): MatchResult? {
        val tpl = loadTemplate(path)
        return TemplateMatcher.findTemplate(frame, tpl, roi, threshold)
    }

    fun findText(frame: ScreenFrame, target: String, matchMode: String, roi: Rect?, minConf: Float): List<TextHit> {
        val engine = ensureOcr()
        val hits = engine.recognize(frame, roi, minConf)
        return TextMatch.filter(hits, target, matchMode)
    }

    fun yoloDetect(
        frame: ScreenFrame,
        modelPath: String,
        conf: Float,
        className: String,
        roi: Rect?,
    ): List<Detection> = yolo.detect(frame, modelPath, conf, className, roi)

    fun pickYolo(detections: List<Detection>, policy: String, anchor: Pair<Int, Int>?): Detection? =
        YoloPick.pick(detections, policy, anchor)

    fun yoloClickPoint(det: Detection, frac: Pair<Float, Float>): Pair<Int, Int> =
        YoloPick.clickPoint(det, frac)

    fun release() {
        yolo.release()
        ocr?.release()
        ocr = null
        templateCache.clear()
    }

    private fun loadTemplate(path: String): ScreenFrame =
        templateCache.getOrPut(path) {
            val bytes = assets.readBytes(path)
            TemplateLoader.fromPngStream(ByteArrayInputStream(bytes))
        }

    private fun ensureOcr(): OcrEngine {
        if (ocr == null) {
            ocr = StubOcrEngine()
        }
        return ocr!!
    }
}
