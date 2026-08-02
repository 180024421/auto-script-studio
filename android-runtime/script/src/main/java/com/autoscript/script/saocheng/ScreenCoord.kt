package com.autoscript.script.saocheng

/** 基准 1280×720 横屏逻辑坐标 → 设备像素（支持 720×1280 竖屏旋转） */
object ScreenCoord {
    const val BASE_W = 1280
    const val BASE_H = 720

    enum class Mode { LANDSCAPE, PORTRAIT }

    fun mode(sw: Int, sh: Int): Mode = if (sh > sw) Mode.PORTRAIT else Mode.LANDSCAPE

    fun scalePoint(x: Float, y: Float, sw: Int, sh: Int, portraitRotCw: Boolean = true): Pair<Int, Int> {
        if (sw == BASE_W && sh == BASE_H) return x.toInt() to y.toInt()
        return when (mode(sw, sh)) {
            Mode.LANDSCAPE -> {
                val sx = (x * sw / BASE_W).toInt()
                val sy = (y * sh / BASE_H).toInt()
                sx to sy
            }
            Mode.PORTRAIT -> {
                if (portraitRotCw) {
                    val sx = (y * sw / BASE_H).toInt()
                    val sy = ((BASE_W - x) * sh / BASE_W).toInt()
                    sx to sy
                } else {
                    val sx = ((BASE_H - y) * sw / BASE_H).toInt()
                    val sy = (x * sh / BASE_W).toInt()
                    sx to sy
                }
            }
        }
    }

    fun scaleLtrb(
        l: Int, t: Int, r: Int, b: Int,
        sw: Int, sh: Int,
        cxOff: Int = 0, cyOff: Int = 0,
        imgW: Int, imgH: Int,
    ): IntArray {
        val (x1, y1) = scalePoint(l.toFloat(), t.toFloat(), sw, sh)
        val (x2, y2) = scalePoint(r.toFloat(), b.toFloat(), sw, sh)
        var l2 = minOf(x1, x2) - cxOff
        var t2 = minOf(y1, y2) - cyOff
        var r2 = maxOf(x1, x2) - cxOff
        var b2 = maxOf(y1, y2) - cyOff
        l2 = l2.coerceIn(0, imgW - 1)
        t2 = t2.coerceIn(0, imgH - 1)
        r2 = r2.coerceAtLeast(l2 + 1).coerceAtMost(imgW)
        b2 = b2.coerceAtLeast(t2 + 1).coerceAtMost(imgH)
        return intArrayOf(l2, t2, r2, b2)
    }
}
