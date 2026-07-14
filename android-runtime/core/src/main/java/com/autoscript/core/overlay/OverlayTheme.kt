package com.autoscript.core.overlay

import android.graphics.Color
import android.graphics.drawable.GradientDrawable

/** 浮动面板视觉主题（与 PC Studio panel_theme_colors 对齐）。 */
enum class OverlayTheme(val id: String) {
    LIGHT("light"),
    GREEN("green"),
    GRAY("gray"),
    DARK("dark"),
    ;

    val panelBackground: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#F8FFFFFF")
            GREEN -> Color.parseColor("#F0FDF4")
            GRAY -> Color.parseColor("#F8FAFC")
            DARK -> Color.parseColor("#E6282830")
        }

    val panelBorder: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#2563EB")
            GREEN -> Color.parseColor("#059669")
            GRAY -> Color.parseColor("#475569")
            DARK -> Color.parseColor("#4CAF50")
        }

    val titleBarBackground: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#2563EB")
            GREEN -> Color.parseColor("#059669")
            GRAY -> Color.parseColor("#475569")
            DARK -> Color.parseColor("#1E2838")
        }

    /** 标题栏文字（与 titleBarBackground 对比）。 */
    val titleBarText: Int
        get() = when (this) {
            LIGHT, GREEN, GRAY -> Color.WHITE
            DARK -> Color.parseColor("#E8EEF6")
        }

    /** 表单正文主色（输入标签、说明文字等）。 */
    val titleText: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#1A2332")
            GREEN -> Color.parseColor("#065F46")
            GRAY -> Color.parseColor("#0F172A")
            DARK -> Color.parseColor("#E8EEF6")
        }

    val logBackground: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#F8FAFC")
            GREEN -> Color.parseColor("#ECFDF5")
            GRAY -> Color.parseColor("#F1F5F9")
            DARK -> Color.parseColor("#CC1A1A1A")
        }

    val logText: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#4A5D75")
            GREEN -> Color.parseColor("#047857")
            GRAY -> Color.parseColor("#64748B")
            DARK -> Color.parseColor("#B0BEC5")
        }

    val ballBackground: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#2563EB")
            GREEN -> Color.parseColor("#059669")
            GRAY -> Color.parseColor("#475569")
            DARK -> Color.parseColor("#4CAF50")
        }

    val ballText: Int
        get() = Color.WHITE

    val accent: Int
        get() = ballBackground

    val sectionBackground: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#F8FAFC")
            GREEN -> Color.WHITE
            GRAY -> Color.WHITE
            // 深色主题提高与面板底的对比
            DARK -> Color.parseColor("#3A3A48")
        }

    val sectionBorder: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#E2E8F0")
            GREEN -> Color.parseColor("#BBF7D0")
            GRAY -> Color.parseColor("#E2E8F0")
            DARK -> Color.parseColor("#6B6B7C")
        }

    val sectionTitle: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#0F172A")
            GREEN -> Color.parseColor("#065F46")
            GRAY -> Color.parseColor("#0F172A")
            DARK -> Color.parseColor("#F1F5F9")
        }

    fun panelDrawable(cornerRadiusPx: Float, strokePx: Int = 2): GradientDrawable =
        GradientDrawable().apply {
            setColor(panelBackground)
            cornerRadius = cornerRadiusPx
            setStroke(strokePx, panelBorder)
        }

    fun titleBarDrawable(cornerRadiusPx: Float): GradientDrawable =
        GradientDrawable().apply {
            setColor(titleBarBackground)
            cornerRadii = floatArrayOf(
                cornerRadiusPx, cornerRadiusPx,
                cornerRadiusPx, cornerRadiusPx,
                0f, 0f,
                0f, 0f,
            )
        }

    fun logDrawable(cornerRadiusPx: Float): GradientDrawable =
        GradientDrawable().apply {
            setColor(logBackground)
            cornerRadius = cornerRadiusPx
            if (this@OverlayTheme != DARK) {
                setStroke(1, sectionBorder)
            }
        }

    fun sectionDrawable(cornerRadiusPx: Float): GradientDrawable =
        GradientDrawable().apply {
            setColor(sectionBackground)
            cornerRadius = cornerRadiusPx
            setStroke(1, sectionBorder)
        }

    fun ballDrawable(): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.OVAL
            setColor(ballBackground)
            if (this@OverlayTheme == LIGHT) {
                setStroke(2, Color.parseColor("#1D4ED8"))
            }
        }

    /** 已点「开始」、待二次确认时的悬浮球样式 */
    fun ballArmedDrawable(): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.OVAL
            setColor(Color.parseColor("#16A34A"))
            setStroke(2, Color.parseColor("#15803D"))
        }

    /** 脚本运行中：悬浮球显示停止图标 */
    fun ballStopDrawable(): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.OVAL
            setColor(Color.parseColor("#DC2626"))
            setStroke(2, Color.parseColor("#B91C1C"))
        }

    fun buttonDrawable(colorHex: String, cornerRadiusPx: Float): GradientDrawable =
        GradientDrawable().apply {
            setColor(parseColorSafe(colorHex))
            cornerRadius = cornerRadiusPx
            if (this@OverlayTheme != DARK) {
                setStroke(1, Color.argb(40, 255, 255, 255))
            }
        }

    /** 次要按钮：描边透明底。 */
    fun buttonOutlineDrawable(colorHex: String, cornerRadiusPx: Float): GradientDrawable =
        GradientDrawable().apply {
            setColor(Color.TRANSPARENT)
            cornerRadius = cornerRadiusPx
            setStroke(2, parseColorSafe(colorHex))
        }

    fun buttonTextColor(colorHex: String): Int {
        val bg = parseColorSafe(colorHex)
        val lum = 0.299 * Color.red(bg) + 0.587 * Color.green(bg) + 0.114 * Color.blue(bg)
        return if (lum > 165) Color.parseColor("#1A2332") else Color.WHITE
    }

    fun parseButtonColor(colorHex: String): Int =
        runCatching { Color.parseColor(colorHex) }.getOrElse { Color.parseColor("#607D8B") }

    companion object {
        fun from(id: String?): OverlayTheme {
            val key = id?.lowercase()?.trim().orEmpty()
            return when (key) {
                "green", "fresh" -> GREEN
                "gray", "grey", "neutral" -> GRAY
                "dark" -> DARK
                else -> LIGHT
            }
        }

        private fun parseColorSafe(hex: String): Int =
            runCatching { Color.parseColor(hex) }.getOrElse { Color.parseColor("#607D8B") }
    }
}
