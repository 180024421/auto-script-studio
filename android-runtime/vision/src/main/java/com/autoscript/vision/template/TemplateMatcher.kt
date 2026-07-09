package com.autoscript.vision.template

import com.autoscript.core.model.MatchResult
import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame
import kotlin.math.roundToInt
import kotlin.math.sqrt

/**
 * 轻量模板匹配（归一化互相关），无 OpenCV 依赖。
 * 支持多尺度：opts.scale_min / scale_max / scale_step。
 */
object TemplateMatcher {

    fun findTemplate(
        frame: ScreenFrame,
        template: ScreenFrame,
        roi: Rect? = null,
        threshold: Float = 0.9f,
        step: Int = 2,
        scaleMin: Float = 1.0f,
        scaleMax: Float = 1.0f,
        scaleStep: Float = 0.1f,
    ): MatchResult? {
        val scales = buildScaleList(scaleMin, scaleMax, scaleStep)
        var best: MatchResult? = null
        for (scale in scales) {
            val tpl = if (scale == 1.0f) template else scaleFrame(template, scale)
            val m = findTemplateAtScale(frame, tpl, roi, threshold, step)
            if (m != null && (best == null || m.score > best.score)) {
                best = m
            }
        }
        return best
    }

    private fun buildScaleList(min: Float, max: Float, step: Float): List<Float> {
        val lo = min.coerceIn(0.5f, 2.0f)
        val hi = max.coerceIn(lo, 2.0f)
        val st = step.coerceIn(0.05f, 0.5f)
        if (hi - lo < 0.01f) return listOf(lo)
        val out = mutableListOf<Float>()
        var s = lo
        while (s <= hi + 0.001f) {
            out.add(((s * 100).roundToInt() / 100f))
            s += st
        }
        return out.distinct()
    }

    private fun findTemplateAtScale(
        frame: ScreenFrame,
        template: ScreenFrame,
        roi: Rect?,
        threshold: Float,
        step: Int,
    ): MatchResult? {
        val stride = step.coerceIn(1, 8)
        val (x1, y1, x2, y2) = roiBounds(frame, roi)
        val tw = template.width
        val th = template.height
        if (tw > (x2 - x1) || th > (y2 - y1)) return null

        val fGray = toGray(frame)
        val tGray = toGray(template)
        val tMean = tGray.average().toFloat()
        val tStd = std(tGray, tMean)
        if (tStd < 1e-6f) return null

        var bestScore = -1f
        var bestX = 0
        var bestY = 0

        for (y in y1 until y2 - th step stride) {
            for (x in x1 until x2 - tw step stride) {
                val score = nccAt(fGray, frame.width, x, y, tw, th, tGray, tMean, tStd)
                if (score > bestScore) {
                    bestScore = score
                    bestX = x
                    bestY = y
                }
            }
        }

        if (bestScore < threshold) return null
        val rect = Rect(bestX, bestY, tw, th)
        return MatchResult(
            centerX = bestX + tw / 2,
            centerY = bestY + th / 2,
            score = bestScore,
            rect = rect,
        )
    }

    private fun scaleFrame(src: ScreenFrame, scale: Float): ScreenFrame {
        if (scale == 1.0f) return src
        val nw = (src.width * scale).roundToInt().coerceAtLeast(1)
        val nh = (src.height * scale).roundToInt().coerceAtLeast(1)
        val bgr = ByteArray(nw * nh * 3)
        for (dy in 0 until nh) {
            val sy = (dy / scale).toInt().coerceIn(0, src.height - 1)
            for (dx in 0 until nw) {
                val sx = (dx / scale).toInt().coerceIn(0, src.width - 1)
                val si = (sy * src.width + sx) * 3
                val di = (dy * nw + dx) * 3
                bgr[di] = src.bgr[si]
                bgr[di + 1] = src.bgr[si + 1]
                bgr[di + 2] = src.bgr[si + 2]
            }
        }
        return ScreenFrame(nw, nh, bgr)
    }

    private fun nccAt(
        fGray: FloatArray,
        frameWidth: Int,
        ox: Int,
        oy: Int,
        tw: Int,
        th: Int,
        tGray: FloatArray,
        tMean: Float,
        tStd: Float,
    ): Float {
        val n = tw * th
        var sum = 0f
        var sumSq = 0f
        var cross = 0f
        var ti = 0
        for (ty in 0 until th) {
            val rowBase = (oy + ty) * frameWidth + ox
            for (tx in 0 until tw) {
                val fv = fGray[rowBase + tx]
                val tv = tGray[ti++]
                sum += fv
                sumSq += fv * fv
                cross += fv * tv
            }
        }
        val fMean = sum / n
        val fVar = sumSq / n - fMean * fMean
        val fStd = sqrt(fVar.coerceAtLeast(0f))
        if (fStd < 1e-6f) return -1f
        cross -= n * fMean * tMean
        return (cross / n) / (fStd * tStd)
    }

    private fun toGray(t: ScreenFrame): FloatArray {
        val n = t.width * t.height
        val out = FloatArray(n)
        for (i in 0 until n) {
            val j = i * 3
            out[i] = gray(t.bgr[j], t.bgr[j + 1], t.bgr[j + 2])
        }
        return out
    }

    private fun std(arr: FloatArray, mean: Float): Float {
        var v = 0f
        for (x in arr) {
            val d = x - mean
            v += d * d
        }
        return sqrt(v / arr.size)
    }

    private fun gray(b: Byte, g: Byte, r: Byte): Float {
        val bi = b.toInt() and 0xFF
        val gi = g.toInt() and 0xFF
        val ri = r.toInt() and 0xFF
        return 0.114f * bi + 0.587f * gi + 0.299f * ri
    }

    private fun roiBounds(frame: ScreenFrame, roi: Rect?): List<Int> {
        if (roi == null) return listOf(0, 0, frame.width, frame.height)
        val r = roi.clamp(frame.width, frame.height)
        return listOf(r.x, r.y, r.x + r.w, r.y + r.h)
    }
}
