package com.autoscript.vision.color

import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame

object ColorFinder {

    fun findColor(
        frame: ScreenFrame,
        targetBgr: Triple<Int, Int, Int>,
        tol: Int = 10,
        roi: Rect? = null,
    ): Pair<Int, Int>? {
        val (tb, tg, tr) = targetBgr
        val bounds = bounds(frame, roi)
        val (x1, y1, x2, y2) = bounds
        for (y in y1 until y2) {
            for (x in x1 until x2) {
                val (b, g, r) = frame.bgrAt(x, y)
                if (kotlin.math.abs(b - tb) <= tol &&
                    kotlin.math.abs(g - tg) <= tol &&
                    kotlin.math.abs(r - tr) <= tol
                ) {
                    return x to y
                }
            }
        }
        return null
    }

    fun multiPointCompare(
        frame: ScreenFrame,
        anchorX: Int,
        anchorY: Int,
        points: List<Triple<Int, Int, Triple<Int, Int, Int>>>,
        tol: Int = 10,
    ): Boolean {
        for ((dx, dy, bgr) in points) {
            val x = anchorX + dx
            val y = anchorY + dy
            if (x !in 0 until frame.width || y !in 0 until frame.height) return false
            val (b, g, r) = frame.bgrAt(x, y)
            val (tb, tg, tr) = bgr
            if (kotlin.math.abs(b - tb) > tol || kotlin.math.abs(g - tg) > tol || kotlin.math.abs(r - tr) > tol) {
                return false
            }
        }
        return true
    }

    private fun bounds(frame: ScreenFrame, roi: Rect?): List<Int> {
        if (roi == null) return listOf(0, 0, frame.width, frame.height)
        val r = roi.clamp(frame.width, frame.height)
        return listOf(r.x, r.y, r.x + r.w, r.y + r.h)
    }
}
