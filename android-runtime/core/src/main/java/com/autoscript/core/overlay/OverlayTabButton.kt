package com.autoscript.core.overlay

import android.content.Context
import android.graphics.Typeface
import android.view.Gravity
import android.widget.TextView

/** 界面标签按钮：用 TextView 避免 Material Button 背景着色导致文字不可见。 */
object OverlayTabButton {
    fun create(
        context: Context,
        theme: OverlayTheme,
        title: String,
        selected: Boolean,
        dp: (Int) -> Int,
        onClick: () -> Unit,
    ): TextView = TextView(context).apply {
        text = title
        textSize = 11f
        isAllCaps = false
        gravity = Gravity.CENTER
        isClickable = true
        isFocusable = true
        val padH = dp(10)
        val padV = dp(6)
        setPadding(padH, padV, padH, padV)
        applyStyle(theme, this, selected, dp)
        setOnClickListener { onClick() }
    }

    fun applyStyle(
        theme: OverlayTheme,
        tv: TextView,
        selected: Boolean,
        dp: (Int) -> Int,
    ) {
        tv.background = if (selected) {
            theme.buttonDrawable("#2563EB", dp(6).toFloat())
        } else {
            theme.logDrawable(dp(6).toFloat())
        }
        tv.setTextColor(
            if (selected) theme.buttonTextColor("#2563EB") else theme.titleText,
        )
        tv.setTypeface(null, if (selected) Typeface.BOLD else Typeface.NORMAL)
    }
}
