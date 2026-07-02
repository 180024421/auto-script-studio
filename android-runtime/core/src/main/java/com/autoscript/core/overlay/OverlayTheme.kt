package com.autoscript.core.overlay

import android.graphics.Color
import android.graphics.drawable.GradientDrawable

/** 浮动面板视觉主题（与 PC Studio 浅色商务风对齐）。 */
enum class OverlayTheme(val id: String) {
    LIGHT("light"),
    DARK("dark"),
    ;

    val panelBackground: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#F8FFFFFF")
            DARK -> Color.parseColor("#E6282830")
        }

    val panelBorder: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#2563EB")
            DARK -> Color.parseColor("#4CAF50")
        }

    val titleBarBackground: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#EFF6FF")
            DARK -> Color.parseColor("#33282830")
        }

    val titleText: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#1A2332")
            DARK -> Color.WHITE
        }

    val logBackground: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#F8FAFC")
            DARK -> Color.parseColor("#CC1A1A1A")
        }

    val logText: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#4A5D75")
            DARK -> Color.parseColor("#B0BEC5")
        }

    val ballBackground: Int
        get() = when (this) {
            LIGHT -> Color.parseColor("#2563EB")
            DARK -> Color.parseColor("#4CAF50")
        }

    val ballText: Int
        get() = when (this) {
            LIGHT -> Color.WHITE
            DARK -> Color.WHITE
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
            if (this@OverlayTheme == LIGHT) {
                setStroke(1, Color.parseColor("#DCE3ED"))
            }
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
            if (this@OverlayTheme == LIGHT) {
                setStroke(1, Color.argb(40, 255, 255, 255))
            }
        }

    fun buttonTextColor(colorHex: String): Int {
        val bg = parseColorSafe(colorHex)
        val lum = 0.299 * Color.red(bg) + 0.587 * Color.green(bg) + 0.114 * Color.blue(bg)
        return if (lum > 165) Color.parseColor("#1A2332") else Color.WHITE
    }

    companion object {
        fun from(id: String?): OverlayTheme =
            entries.firstOrNull { it.id.equals(id, ignoreCase = true) } ?: LIGHT

        private fun parseColorSafe(hex: String): Int =
            runCatching { Color.parseColor(hex) }.getOrElse { Color.parseColor("#607D8B") }
    }
}
