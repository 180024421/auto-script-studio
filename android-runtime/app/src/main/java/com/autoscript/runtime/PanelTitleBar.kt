package com.autoscript.runtime

import android.content.Context
import android.graphics.Color
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.TextView

/** 与 PC Studio 预览一致的居中标题栏（layout.json panel.title）。 */
object PanelTitleBar {

    fun create(
        context: Context,
        title: String,
        dp: (Int) -> Int,
    ): TextView = TextView(context).apply {
        text = title
        textSize = 14f
        paint.isFakeBoldText = true
        gravity = Gravity.CENTER
        textAlignment = android.view.View.TEXT_ALIGNMENT_CENTER
        setTextColor(Color.WHITE)
        setBackgroundColor(Color.parseColor("#2563EB"))
        setPadding(dp(10), dp(8), dp(10), dp(8))
        layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        )
    }
}
