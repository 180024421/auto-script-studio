package com.autoscript.vision

import android.content.Context
import com.autoscript.core.model.Detection
import com.autoscript.core.model.MatchResult
import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame
import com.autoscript.core.model.TextHit
import com.autoscript.core.project.PerfConfig
import com.autoscript.core.project.ProjectAssets
import com.autoscript.vision.color.ColorFinder
import com.autoscript.vision.ocr.MlKitOcrEngine
import com.autoscript.vision.ocr.OcrEngine
import com.autoscript.vision.ocr.TextMatch
import com.autoscript.vision.template.TemplateLoader
import com.autoscript.vision.template.TemplateMatcher
import com.autoscript.vision.yolo.OnnxYoloDetector
import com.autoscript.vision.yolo.YoloDetector
import com.autoscript.vision.yolo.YoloPick
import java.io.ByteArrayInputStream

class VisionEngine(
    private val assets: ProjectAssets,
    appContext: Context,
    ocrMode: String = "lazy",
    yoloImgsz: Int = 320,
    perf: PerfConfig = PerfConfig(),
) {
    private val templateCache = mutableMapOf<String, ScreenFrame>()
    private val yolo: YoloDetector = OnnxYoloDetector(appContext, assets, yoloImgsz, useNnapi = perf.yoloNnapi)
    private var ocr: OcrEngine? = when (ocrMode) {
        "disabled" -> null
        "eager" -> MlKitOcrEngine(appContext)
        else -> null
    }
    private val ocrMode = ocrMode
    private val appContext = appContext.applicationContext

    fun findColor(frame: ScreenFrame, bgr: Triple<Int, Int, Int>, tol: Int, roi: Rect?): Pair<Int, Int>? =
        ColorFinder.findColor(frame, bgr, tol, roi)

    fun findTemplate(
        frame: ScreenFrame,
        path: String,
        threshold: Float,
        roi: Rect?,
        step: Int = 2,
    ): MatchResult? {
        val tpl = loadTemplate(path)
        return TemplateMatcher.findTemplate(frame, tpl, roi, threshold, step)
    }

    fun recognizeAll(frame: ScreenFrame, roi: Rect?, minConf: Float): List<TextHit> {
        val engine = ensureOcr()
        return engine.recognize(frame, roi, minConf)
    }

    fun findText(frame: ScreenFrame, target: String, matchMode: String, roi: Rect?, minConf: Float): List<TextHit> {
        val hits = recognizeAll(frame, roi, minConf)
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
            ocr = MlKitOcrEngine(appContext)
        }
        return ocr!!
    }
}
