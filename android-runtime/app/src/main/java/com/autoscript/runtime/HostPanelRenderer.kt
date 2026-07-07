package com.autoscript.runtime

import android.content.Context
import android.view.View
import android.widget.LinearLayout
import com.autoscript.core.overlay.LayoutConfig
import com.autoscript.core.overlay.OverlayTheme

/**
 * 在 APK 主页面渲染 layout.json 中的表单界面（screens），不含 chrome 启停按钮。
 */
class HostPanelRenderer(
    private val context: Context,
    private var layoutConfig: LayoutConfig,
    private val dp: (Int) -> Int,
    private val panelWidthPx: Int,
    private val onActiveScreenChange: (Int) -> Unit = {},
) {
    fun build(): View {
        val theme = OverlayTheme.from(layoutConfig.panel.theme)
        val builder = OverlayPanelBuilder(
            context = context,
            theme = theme,
            onAction = {},
            dp = dp,
        )
        val root = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            background = theme.panelDrawable(dp(12).toFloat())
        }
        root.addView(PanelTitleBar.create(context, layoutConfig.panel.title, dp))
        if (layoutConfig.isFreeMode() && layoutConfig.resolvedScreens().isNotEmpty()) {
            val screenPanel = OverlayScreenPanelBuilder(
                context = context,
                theme = theme,
                layoutConfig = layoutConfig,
                widgetBuilder = builder,
                dp = dp,
                panelWidthPx = panelWidthPx,
                onActiveScreenChange = { idx ->
                    layoutConfig = layoutConfig.copy(
                        panel = layoutConfig.panel.copy(activeScreen = idx),
                    )
                    onActiveScreenChange(idx)
                },
                includeChrome = false,
            ).build()
            root.addView(
                screenPanel,
                LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ),
            )
        } else {
            val cols = layoutConfig.panel.columns.coerceIn(1, 3)
            val widgets = layoutConfig.resolvedScreens()
                .flatMap { it.widgets }
                .filter { !it.isActionControl() }
            root.addView(builder.buildContentGrid(widgets, cols))
        }
        return root
    }
}
