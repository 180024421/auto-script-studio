package com.autoscript.runtime

import android.content.Context
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.ScrollView
import com.autoscript.core.overlay.LayoutConfig
import com.autoscript.core.overlay.OverlayTabButton
import com.autoscript.core.overlay.OverlayTheme
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
    private val panelWidthPx: Int,
    private val onActiveScreenChange: (Int) -> Unit,
    private val includeChrome: Boolean = true,
    private val freeDesignMode: Boolean = false,
    private val freeDesignCallbacks: FreeOverlayDesignCallbacks? = null,
) {
    private var activeScreen: Int = layoutConfig.activeScreenIndex()
    private lateinit var contentFrame: FrameLayout
    private lateinit var tabBar: LinearLayout
    private lateinit var tabScroll: HorizontalScrollView

    fun build(): LinearLayout {
        val root = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
        }
        tabBar = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(4), dp(4), dp(4), dp(4))
            setBackgroundColor(0xFFF1F5F9.toInt())
        }
        tabScroll = HorizontalScrollView(context).apply {
            isHorizontalScrollBarEnabled = false
            overScrollMode = android.view.View.OVER_SCROLL_IF_CONTENT_SCROLLS
            setBackgroundColor(0xFFF1F5F9.toInt())
            addView(
                tabBar,
                ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                    ViewGroup.LayoutParams.MATCH_PARENT,
                ),
            )
        }
        root.addView(tabScroll, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        ))
        rebuildTabButtons()

        val scroll = ScrollView(context).apply {
            isFillViewport = true
        }
        contentFrame = FrameLayout(context).apply {
            clipChildren = true
            clipToPadding = true
        }
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

        if (includeChrome) {
            val chrome = layoutConfig.chromeWidgets()
            if (chrome.isNotEmpty()) {
                val chromeDesignH = chrome.maxOf { it.layoutY + it.layoutH }.coerceAtLeast(64)
                val chromeHost = FrameLayout(context).apply {
                    clipChildren = true
                    clipToPadding = true
                    setPadding(dp(4), dp(4), dp(4), dp(4))
                    setBackgroundColor(0xFFF8FAFC.toInt())
                }
                val chromeH = scaleY(chromeDesignH).coerceAtLeast(dp(52))
                chromeHost.layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    chromeH,
                )
                placeFreeWidgets(chromeHost, chrome, chromeDesignH)
                root.addView(chromeHost)
            }
        }
        return root
    }

    private fun rebuildTabButtons() {
        tabBar.removeAllViews()
        layoutConfig.resolvedScreens().forEachIndexed { index, sc ->
            val btn = OverlayTabButton.create(
                context = context,
                theme = theme,
                title = sc.title,
                selected = index == activeScreen,
                dp = dp,
            ) {
                if (activeScreen != index) {
                    activeScreen = index
                    onActiveScreenChange(index)
                    rebuildTabButtons()
                    renderActiveScreen()
                    tabBar.post {
                        tabScroll.smoothScrollTo(tabBar.getChildAt(index).left, 0)
                    }
                }
            }
            btn.layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { marginEnd = dp(4) }
            tabBar.addView(btn)
        }
        tabBar.post {
            val idx = activeScreen.coerceIn(0, layoutConfig.resolvedScreens().size - 1)
            if (idx > 0 && tabBar.childCount > idx) {
                tabScroll.smoothScrollTo(tabBar.getChildAt(idx).left, 0)
            }
        }
    }

    private fun formWidgetsForScreen(screenIdx: Int): List<WidgetConfig> {
        val raw = layoutConfig.screenWidgets(screenIdx)
        return if (!includeChrome) raw.filter { !it.isActionControl() } else raw
    }

    private fun renderActiveScreen() {
        contentFrame.removeAllViews()
        val widgets = formWidgetsForScreen(activeScreen)
        val contentDesignH = if (widgets.isEmpty()) 800 else {
            widgets.maxOf { it.layoutY + it.layoutH } + 80
        }
        val placedH = placeFreeWidgets(contentFrame, widgets, contentDesignH)
        contentFrame.layoutParams = FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            placedH.coerceAtLeast(dp(240)),
        )
    }

    private fun placeFreeWidgets(
        host: FrameLayout,
        widgets: List<WidgetConfig>,
        hostDesignH: Int,
    ): Int {
        val scaleX = scaleFactorX()
        val scaleY = scaleFactorY(hostDesignH)
        var maxBottom = 0
        widgetBuilder.freeLayoutPlacement = true
        widgetBuilder.uiScale = scaleX
        try {
            widgets.forEachIndexed { index, cfg ->
                val minH = dp(minWidgetHeightDp(cfg.type))
                val w = (cfg.layoutW * scaleX).toInt().coerceIn(dp(40), panelWidthPx)
                val h = (cfg.layoutH * scaleY).toInt().coerceAtLeast(minH)
                val top = (cfg.layoutY * scaleY).toInt().coerceAtLeast(0)
                val left = (cfg.layoutX * scaleX).toInt().coerceAtLeast(0)

                val inner = widgetBuilder.buildWidget(cfg, 2, listOf(activeScreen, index))
                val widgetPath = listOf(activeScreen, index)
                val contentHost = FrameLayout(context).apply {
                    clipChildren = true
                    addView(
                        inner,
                        FrameLayout.LayoutParams(
                            FrameLayout.LayoutParams.MATCH_PARENT,
                            FrameLayout.LayoutParams.MATCH_PARENT,
                        ),
                    )
                }
                val slot: View = if (freeDesignMode && freeDesignCallbacks != null) {
                    FreeOverlayDesignFrame(
                        context = context,
                        widgetPath = widgetPath,
                        designW = layoutConfig.panel.designWidth,
                        designH = layoutConfig.panel.designHeight,
                        scaleX = scaleX,
                        scaleY = scaleY,
                        callbacks = freeDesignCallbacks,
                        dp = dp,
                        content = contentHost,
                        showDragHandle = !FreeOverlayDesignFrame.isFormLikeWidget(cfg.type),
                    )
                } else {
                    contentHost
                }
                host.addView(
                    slot,
                    FrameLayout.LayoutParams(w, h).apply {
                        leftMargin = left
                        topMargin = top
                        gravity = Gravity.START or Gravity.TOP
                    },
                )
                maxBottom = maxOf(maxBottom, top + h)
            }
        } finally {
            widgetBuilder.freeLayoutPlacement = false
            widgetBuilder.uiScale = 1f
        }
        return maxBottom.coerceAtLeast(scaleY(hostDesignH))
    }

    private fun minWidgetHeightDp(type: String): Int = when (type) {
        "input", "select", "radio", "multiselect" -> 48
        "textarea" -> 72
        "switch", "slider", "stepper", "time_range" -> 44
        "text", "label" -> 28
        "divider" -> 8
        "start_script", "stop_script", "collapse", "tap", "lua" -> 40
        else -> 36
    }

    private fun scaleFactorX(): Float {
        val designW = layoutConfig.panel.designWidth.coerceAtLeast(1)
        val panelW = panelWidthPx.coerceAtLeast(1)
        return panelW.toFloat() / designW.toFloat()
    }

    private fun scaleFactorY(contentDesignH: Int): Float {
        val viewH = scaleY(contentDesignH).coerceAtLeast(1)
        return viewH.toFloat() / contentDesignH.coerceAtLeast(1).toFloat()
    }

    private fun scaleY(v: Int): Int = (v * scaleFactorX()).toInt()
}
