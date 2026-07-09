package com.autoscript.core.model

data class Rect(val x: Int, val y: Int, val w: Int, val h: Int) {
    fun clamp(maxW: Int, maxH: Int): Rect {
        val x1 = x.coerceIn(0, maxW)
        val y1 = y.coerceIn(0, maxH)
        val x2 = (x + w).coerceIn(0, maxW)
        val y2 = (y + h).coerceIn(0, maxH)
        return Rect(x1, y1, (x2 - x1).coerceAtLeast(0), (y2 - y1).coerceAtLeast(0))
    }
}

data class ScreenFrame(
    val width: Int,
    val height: Int,
    /** BGR row-major bytes, length = width * height * 3 */
    val bgr: ByteArray,
    /** True when [bgr] is reused by the capture pipeline; call [copy] before retaining. */
    val sharedBuffer: Boolean = false,
) {
    /** Deep-copies pixel data for consumers that outlive the next capture. */
    fun copy(): ScreenFrame = ScreenFrame(width, height, bgr.copyOf(), sharedBuffer = false)

    fun bgrAt(x: Int, y: Int): Triple<Int, Int, Int> {
        val i = (y * width + x) * 3
        return Triple(
            bgr[i].toInt() and 0xFF,
            bgr[i + 1].toInt() and 0xFF,
            bgr[i + 2].toInt() and 0xFF,
        )
    }
}

data class MatchResult(
    val centerX: Int,
    val centerY: Int,
    val score: Float,
    val rect: Rect,
)

data class Detection(
    val className: String,
    val confidence: Float,
    val rect: Rect,
    /** YOLO-seg 模型是否成功解码出实例掩码 */
    val hasMask: Boolean = false,
    /** 掩码质心（屏幕坐标），不规则目标比框中心更准 */
    val maskCenterX: Int? = null,
    val maskCenterY: Int? = null,
    /** 掩码前景像素数（屏幕坐标下采样统计） */
    val maskArea: Int = 0,
)

data class TextHit(
    val text: String,
    val centerX: Int,
    val centerY: Int,
    val confidence: Float,
    val rect: Rect,
)
