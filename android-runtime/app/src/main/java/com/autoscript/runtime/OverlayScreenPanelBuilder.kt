package com.autoscript.runtime

import android.content.Context
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.ScrollView
import com.autoscript.core.overlay.LayoutConfig
import com.autoscript.core.overlay.OverlayTheme
import com.autoscript.core.overlay.ScreenConfig
import com.autoscript.core.overlay.WidgetConfig

/**
 * 全局标签页 + 可滚动界面 + 自由坐标（layout_x/y/w/h）渲染。
 */
class OverlayScreenPanelBuilder(
    private val context: Context,
    private val theme: OverlayTheme,
    private val layoutConfig: LayoutConfig,
    private val widgetBuilder: OverlayPanelBuilder,
    private val dp: (Int) -> Int,
    private val onActiveScreenChange: (Int) -> Unit,
) {
    private var activeScreen: Int = layoutConfig.activeScreenIndex()
    private lateinit var contentFrame: FrameLayout
    private lateinit var tabBar: LinearLayout

    fun build(): LinearLayout {
        val root = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
        }
        tabBar = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(4), dp(4), dp(4), dp(4))
            setBackgroundColor(0xFFF1F5F9.toInt())
        }
        root.addView(tabBar, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        ))
        rebuildTabButtons()

        val scroll = ScrollView(context).apply {
            isFillViewport = true
        }
        contentFrame = FrameLayout(context)
        scroll.addView(contentFrame, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.WRAP_CONTENT,
        ))
        root.addView(scroll, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            0,
            1f,
        ))
        renderActiveScreen()

        val chrome = layoutConfig.chromeWidgets()
        if (chrome.isNotEmpty()) {
            val chromeHost = FrameLayout(context).apply {
                setPadding(dp(4), dp(4), dp(4), dp(4))
                setBackgroundColor(0xFFF8FAFC.toInt())
            }
            val chromeH = dp(64)
            chromeHost.layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                chromeH,
            )
            placeFreeWidgets(chromeHost, chrome, chromeH)
            root.addView(chromeHost)
        }
        return root
    }

    private fun rebuildTabButtons() {
        tabBar.removeAllViews()
        layoutConfig.resolvedScreens().forEachIndexed { index, sc ->
            val btn = Button(context).apply {
                text = sc.title
                textSize = 11f
                isAllCaps = false
                stateListAnimator = null
                elevation = 0f
                minHeight = dp(32)
                val on = index == activeScreen
                background = if (on) theme.buttonDrawable("#2563EB", dp(6).toFloat())
                else theme.logDrawable(dp(6).toFloat())
                setTextColor(if (on) theme.buttonTextColor("#2563EB") else theme.logText)
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ).apply { marginEnd = dp(4) }
                setOnClickListener {
                    if (activeScreen != index) {
                        activeScreen = index
                        onActiveScreenChange(index)
                        rebuildTabButtons()
                        renderActiveScreen()
                    }
                }
            }
            tabBar.addView(btn)
        }
    }

    private fun renderActiveScreen() {
        contentFrame.removeAllViews()
        val widgets = layoutConfig.screenWidgets(activeScreen)
        val contentH = contentHeightPx(widgets)
        contentFrame.layoutParams = FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            contentH,
        )
        placeFreeWidgets(contentFrame, widgets, contentH)
    }

    private fun contentHeightPx(widgets: List<WidgetConfig>): Int {
        val designH = if (widgets.isEmpty()) 800 else {
            widgets.maxOf { it.layoutY + it.layoutH } + 80
        }
        return scaleY(designH).coerceAtLeast(dp(240))
    }

    private fun placeFreeWidgets(host: FrameLayout, widgets: List<WidgetConfig>, hostDesignH: Int) {
        val scaleX = scaleFactorX()
        val scaleY = scaleFactorY(hostDesignH)
        widgets.forEachIndexed { index, cfg ->
            val inner = widgetBuilder.buildWidget(cfg, 2, listOf(activeScreen, index))
            val lp = FrameLayout.LayoutParams(
                (cfg.layoutW * scaleX).toInt().coerceAtLeast(dp(48)),
                (cfg.layoutH * scaleY).toInt().coerceAtLeast(dp(28)),
            ).apply {
                leftMargin = (cfg.layoutX * scaleX).toInt()
                topMargin = (cfg.layoutY * scaleY).toInt()
            }
            host.addView(inner, lp)
        }
    }

    private fun scaleFactorX(): Float {
        val designW = layoutConfig.panel.designWidth.coerceAtLeast(1)
        val panelW = dp(layoutConfig.panel.widthDp).coerceAtLeast(1)
        return panelW.toFloat() / designW.toFloat()
    }

    private fun scaleFactorY(contentDesignH: Int): Float {
        val designH = layoutConfig.panel.designHeight.coerceAtLeast(1)
        val viewH = scaleY(contentDesignH).coerceAtLeast(1)
        return viewH.toFloat() / contentDesignH.coerceAtLeast(1).toFloat()
    }

    private fun scaleY(v: Int): Int = (v * scaleFactorX()).toInt()
}
