package com.autoscript.vision.template

import com.autoscript.core.model.MatchResult
import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame
import kotlin.math.sqrt

/**
 * 轻量模板匹配（归一化互相关），无 OpenCV 依赖。
 */
object TemplateMatcher {

    fun findTemplate(
        frame: ScreenFrame,
        template: ScreenFrame,
        roi: Rect? = null,
        threshold: Float = 0.9f,
    ): MatchResult? {
        val (x1, y1, x2, y2) = roiBounds(frame, roi)
        val tw = template.width
        val th = template.height
        if (tw > (x2 - x1) || th > (y2 - y1)) return null

        val tGray = toGray(template)
        val tMean = tGray.average().toFloat()
        val tStd = std(tGray, tMean)
        if (tStd < 1e-6f) return null

        var bestScore = -1f
        var bestX = 0
        var bestY = 0

        for (y in y1 until y2 - th) {
            for (x in x1 until x2 - tw) {
                val score = nccAt(frame, x, y, tw, th, tGray, tMean, tStd)
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

    private fun nccAt(
        frame: ScreenFrame,
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
            for (tx in 0 until tw) {
                val fv = grayAt(frame, ox + tx, oy + ty)
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
        cross = 0f
        ti = 0
        for (ty in 0 until th) {
            for (tx in 0 until tw) {
                val fv = grayAt(frame, ox + tx, oy + ty)
                cross += (fv - fMean) * (tGray[ti++] - tMean)
            }
        }
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

    private fun grayAt(frame: ScreenFrame, x: Int, y: Int): Float {
        val j = (y * frame.width + x) * 3
        return gray(frame.bgr[j], frame.bgr[j + 1], frame.bgr[j + 2])
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
