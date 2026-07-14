package com.autoscript.runtime

import android.content.Context
import android.graphics.Color
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import com.autoscript.core.overlay.LayoutConfig
import com.autoscript.core.overlay.LayoutEditorOps
import com.autoscript.core.overlay.LayoutOverrideStore
import com.autoscript.core.overlay.OverlayTheme
import kotlin.math.abs

/**
 * 在 APK 主页面渲染 layout.json 表单；支持长按标题进入 free/grid 设计模式并保存覆盖。
 */
class HostPanelRenderer(
    private val context: Context,
    private var layoutConfig: LayoutConfig,
    private val dp: (Int) -> Int,
    private val panelWidthPx: Int,
    private val onActiveScreenChange: (Int) -> Unit = {},
    private val onLayoutChanged: (LayoutConfig) -> Unit = {},
    private val onLog: (String) -> Unit = {},
) {
    private var designMode = false
    private var selectedWidgetPath: List<Int>? = null
    private val handler = Handler(Looper.getMainLooper())

    private val freeDesignCallbacks = object : FreeOverlayDesignCallbacks {
        override fun onSelect(widgetPath: List<Int>) {
            selectedWidgetPath = widgetPath
        }

        override fun onRectChange(widgetPath: List<Int>, x: Int, y: Int, w: Int, h: Int) {
            val before = layoutConfig
            var next = LayoutEditorOps.setWidgetRect(layoutConfig, widgetPath, x, y, w, h)
            next = LayoutEditorOps.offsetSectionContents(before, next, widgetPath, x, y)
            layoutConfig = next
            onLayoutChanged(layoutConfig)
            rebuildRoot()?.let { /* replaced by caller via onLayoutChanged+rebuild */ }
        }
    }

    private val gridDesignCallbacks = object : OverlayDesignCallbacks {
        override fun onReorder(containerPath: List<Int>, from: Int, to: Int) {
            layoutConfig = LayoutEditorOps.reorderInContainer(layoutConfig, containerPath, from, to)
            onLayoutChanged(layoutConfig)
        }

        override fun onSpanChange(widgetPath: List<Int>, width: Int) {
            layoutConfig = LayoutEditorOps.setWidgetWidth(layoutConfig, widgetPath, width)
            onLayoutChanged(layoutConfig)
        }

        override fun onSelect(widgetPath: List<Int>) {
            selectedWidgetPath = widgetPath
        }
    }

    /** 由 MainActivity 设置：替换 host 容器内容。 */
    var onRequestRebuild: (() -> Unit)? = null

    fun currentLayout(): LayoutConfig = layoutConfig

    fun isDesignMode(): Boolean = designMode

    /** 重建后保留设计态（MainActivity.setupHostPanel 使用）。 */
    fun forceDesignMode(enabled: Boolean) {
        designMode = enabled
        if (!enabled) selectedWidgetPath = null
    }

    fun build(): View {
        val theme = OverlayTheme.from(layoutConfig.panel.theme)
        val builder = OverlayPanelBuilder(
            context = context,
            theme = theme,
            onAction = {},
            dp = dp,
            designMode = designMode && !layoutConfig.isFreeMode(),
            designCallbacks = if (designMode && !layoutConfig.isFreeMode()) gridDesignCallbacks else null,
        )
        val root = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            background = theme.panelDrawable(dp(12).toFloat())
        }
        val title = PanelTitleBar.create(
            context,
            layoutConfig.panel.title + if (designMode) " · 设计中" else "",
            dp,
            theme,
        )
        if (layoutConfig.panel.allowDesign) {
            attachTitleLongPress(title) { toggleDesignMode() }
        }
        root.addView(title)
        if (designMode) {
            root.addView(buildDesignToolbar(theme))
        }
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
                    onLayoutChanged(layoutConfig)
                },
                includeChrome = false,
                freeDesignMode = designMode,
                freeDesignCallbacks = if (designMode) freeDesignCallbacks else null,
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

    private fun rebuildRoot(): View? {
        onRequestRebuild?.invoke()
        return null
    }

    private fun toggleDesignMode() {
        if (!layoutConfig.panel.allowDesign) return
        designMode = !designMode
        if (!designMode) selectedWidgetPath = null
        onLog(if (designMode) "已进入主页面布局设计模式（长按标题可切换）" else "已退出布局设计模式")
        onRequestRebuild?.invoke()
    }

    private fun exitDesignMode() {
        designMode = false
        selectedWidgetPath = null
        onLog("已退出布局设计模式")
        onRequestRebuild?.invoke()
    }

    private fun saveDesignLayout() {
        val file = LayoutOverrideStore.save(context, layoutConfig)
        Toast.makeText(context, "布局已保存", Toast.LENGTH_SHORT).show()
        onLog("布局已保存: ${file.absolutePath}")
    }

    private fun buildDesignToolbar(theme: OverlayTheme): LinearLayout =
        LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(8), dp(4), dp(8), dp(4))
            setBackgroundColor(Color.parseColor("#EFF6FF"))
            addView(
                TextView(context).apply {
                    text = "设计模式：拖动控件 · 保存后可用 Studio 拉取"
                    setTextColor(theme.titleText)
                    textSize = 12f
                    paint.isFakeBoldText = true
                    layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                },
            )
            addView(
                Button(context).apply {
                    text = "保存"
                    textSize = 11f
                    isAllCaps = false
                    stateListAnimator = null
                    elevation = 0f
                    minHeight = dp(32)
                    background = theme.buttonDrawable("#2563EB", dp(6).toFloat())
                    setTextColor(theme.buttonTextColor("#2563EB"))
                    setOnClickListener { saveDesignLayout() }
                },
            )
            addView(
                Button(context).apply {
                    text = "退出"
                    textSize = 11f
                    isAllCaps = false
                    stateListAnimator = null
                    elevation = 0f
                    minHeight = dp(32)
                    layoutParams = LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.WRAP_CONTENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT,
                    ).apply { marginStart = dp(6) }
                    background = theme.logDrawable(dp(6).toFloat())
                    setTextColor(theme.logText)
                    setOnClickListener { exitDesignMode() }
                },
            )
        }

    @android.annotation.SuppressLint("ClickableViewAccessibility")
    private fun attachTitleLongPress(view: View, onLongPress: () -> Unit) {
        var downX = 0f
        var downY = 0f
        var moved = false
        var fired = false
        val runnable = Runnable {
            if (!moved) {
                fired = true
                onLongPress()
            }
        }
        view.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    downX = event.rawX
                    downY = event.rawY
                    moved = false
                    fired = false
                    handler.postDelayed(runnable, 1200)
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    if (abs(event.rawX - downX) > 8 || abs(event.rawY - downY) > 8) {
                        moved = true
                        handler.removeCallbacks(runnable)
                    }
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    handler.removeCallbacks(runnable)
                    true
                }
                else -> false
            }
        }
    }

}
