package com.autoscript.runtime

import android.content.Context
import android.graphics.Color
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.TextView
import com.autoscript.core.overlay.OverlayTheme

/** 与 PC Studio 预览一致的居中标题栏（layout.json panel.title，固定 48dp）。 */
object PanelTitleBar {

    private const val TITLE_DP = 48

    fun create(
        context: Context,
        title: String,
        dp: (Int) -> Int,
        theme: OverlayTheme = OverlayTheme.LIGHT,
    ): TextView = TextView(context).apply {
        text = title
        textSize = 13f
        paint.isFakeBoldText = true
        gravity = Gravity.CENTER
        textAlignment = android.view.View.TEXT_ALIGNMENT_CENTER
        setTextColor(titleForeground(theme))
        setBackgroundColor(titleBackground(theme))
        setPadding(dp(10), 0, dp(10), 0)
        minimumHeight = dp(TITLE_DP)
        layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            dp(TITLE_DP),
        )
    }

    private fun titleBackground(theme: OverlayTheme): Int = theme.titleBarBackground

    private fun titleForeground(theme: OverlayTheme): Int = theme.titleBarText
}
