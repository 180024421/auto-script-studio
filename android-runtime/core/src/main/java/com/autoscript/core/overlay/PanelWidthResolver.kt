package com.autoscript.core.overlay

/**
 * 解析浮动面板在设备上的实际像素宽度。
 *
 * - fixed：width_dp 为 Android dp（按键精灵式窄条）
 * - auto：width_dp 为设计稿像素宽度，按屏幕宽度等比缩放（720 屏 + width_dp=648 → 约 90% 屏宽）
 */
object PanelWidthResolver {
    fun resolveWidthPx(
        panel: PanelConfig,
        screenWidthPx: Int,
        dp: (Int) -> Int,
    ): Int {
        val margin = dp(12)
        val maxW = (screenWidthPx - margin * 2).coerceAtLeast(dp(120))
        val minW = dp(160)
        return when (panel.widthMode.lowercase()) {
            "auto", "design" -> {
                val design = panel.designWidth.coerceAtLeast(1)
                val targetOnDesign = panel.widthDp.coerceIn(160, design)
                val scaled = (screenWidthPx.toFloat() * targetOnDesign / design.toFloat()).toInt()
                scaled.coerceIn(minW, maxW)
            }
            else -> dp(panel.widthDp).coerceIn(minW, maxW)
        }
    }
}
