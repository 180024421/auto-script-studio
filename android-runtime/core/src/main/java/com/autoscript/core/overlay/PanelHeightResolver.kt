package com.autoscript.core.overlay

/**
 * 解析浮动面板在设备上的实际像素高度。
 *
 * - wrap：由内容决定（WindowManager WRAP_CONTENT）
 * - full：占满可用屏高
 * - auto：height_dp 为设计稿像素高度，按屏高等比缩放
 */
object PanelHeightResolver {
    fun resolveHeightPx(
        panel: PanelConfig,
        screenHeightPx: Int,
        dp: (Int) -> Int,
    ): Int? {
        val margin = dp(8)
        val maxH = (screenHeightPx - margin * 2).coerceAtLeast(dp(200))
        val minH = dp(200)
        return when (panel.heightMode.lowercase()) {
            "full" -> maxH
            "auto", "design" -> {
                val design = panel.designHeight.coerceAtLeast(1)
                val targetOnDesign = panel.heightDp.coerceIn(200, design)
                val scaled = (screenHeightPx.toFloat() * targetOnDesign / design.toFloat()).toInt()
                scaled.coerceIn(minH, maxH)
            }
            else -> null
        }
    }
}
