package com.autoscript.runtime

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.Build
import android.provider.Settings
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.core.app.NotificationCompat
import com.autoscript.core.backend.DeviceAutomationBackend
import com.autoscript.core.log.ScriptLog
import com.autoscript.core.log.ScriptStatus
import com.autoscript.core.overlay.LayoutConfig
import com.autoscript.core.overlay.LayoutEditorOps
import com.autoscript.core.overlay.LayoutOverrideStore
import com.autoscript.core.overlay.OverlayWidgetStore
import com.autoscript.core.overlay.OverlayTheme
import com.autoscript.core.overlay.PanelHeightResolver
import com.autoscript.core.overlay.PanelWidthResolver
import com.autoscript.core.overlay.WidgetConfig
import com.autoscript.core.project.ProjectAssets
import android.graphics.BitmapFactory
import android.graphics.PorterDuff
import android.widget.FrameLayout
import android.widget.ImageView
import com.autoscript.core.script.ScriptCancelToken
import com.autoscript.script.lua.LuaSnippetRunner
import kotlin.math.abs
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/**
 * 按键精灵式浮动控制面板：可拖拽、可收起为小球、按钮布局由 ui/layout.json 定义。
 */
class OverlayService : Service() {

    private lateinit var wm: WindowManager
    private var panelView: View? = null
    private var ballView: View? = null
    private var logView: TextView? = null
    private var titleDragHandle: View? = null
    private var layoutParams: WindowManager.LayoutParams? = null
    private var ballParams: WindowManager.LayoutParams? = null
    private var collapsed = false
    private var startArmed = false
    private var scriptRunning = false
    private var ballImageView: ImageView? = null
    private var ballFallbackView: TextView? = null
    private var ballBadgeView: TextView? = null
    private var ballUsesImage = false
    private var unifiedMinimalBar = false
    private var minimalControlsWrap: View? = null
    private var minimalControlsFrame: FrameLayout? = null
    private var minimalLogWrap: View? = null
    private var minimalLogToggle: View? = null
    private var minimalToolbarRow: LinearLayout? = null
    private var minimalLogExpanded = false
    private var minimalBallHost: View? = null
    private var restoreCollapsedAfterBuild = false
    private var layoutConfig: LayoutConfig = LayoutConfig.DEFAULT
    private var panelWidthPx: Int = 0
    private var panelHeightPx: Int? = null
    private var designMode = false
    private var selectedWidgetPath: List<Int>? = null
    private val scope = CoroutineScope(Dispatchers.Main)
    private var snippetJob: Job? = null
    private val handler = Handler(Looper.getMainLooper())
    private var statusPollActive = false
    private val idleCollapseRunnable = Runnable { onIdleCollapse() }
    private val logPending = StringBuilder()
    private val logFlushRunnable = Runnable { flushPendingLog() }
    private val scriptRunningListener: (Boolean) -> Unit = { running ->
        handler.post {
            if (running != scriptRunning) {
                scriptRunning = running
                updateBallAppearance()
            }
        }
    }
    private val statusPollRunnable = object : Runnable {
        override fun run() {
            val running = ScriptStatus.isRunning(this@OverlayService)
            if (running != scriptRunning) {
                scriptRunning = running
                updateBallAppearance()
            }
            handler.postDelayed(this, 1500)
        }
    }

    private val designCallbacks = object : OverlayDesignCallbacks {
        override fun onReorder(containerPath: List<Int>, from: Int, to: Int) {
            layoutConfig = LayoutEditorOps.reorderInContainer(layoutConfig, containerPath, from, to)
            rebuildPanel()
        }

        override fun onSpanChange(widgetPath: List<Int>, span: Int) {
            layoutConfig = LayoutEditorOps.setWidgetWidth(layoutConfig, widgetPath, span)
            rebuildPanel()
        }

        override fun onSelect(widgetPath: List<Int>) {
            selectedWidgetPath = widgetPath
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        wm = getSystemService(WINDOW_SERVICE) as WindowManager
        layoutConfig = loadLayout()
        OverlayWidgetStore.seedFromLayout(layoutConfig)
        startForeground(NOTIFICATION_ID, buildNotification("浮动面板运行中"))
        if (layoutConfig.enabled && layoutConfig.panel.showOnLaunch) {
            if (showOverlay()) {
                startStatusTracking()
            } else {
                ScriptLog.w("无悬浮窗权限或窗口创建失败，已跳过启动时自动显示面板")
            }
        }
        ScriptStatus.addRunningListener(scriptRunningListener)
        scriptRunning = ScriptStatus.isRunning(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_TOGGLE -> toggleCollapse()
            ACTION_RELOAD -> {
                removeOverlay()
                layoutModeReset()
                layoutConfig = loadLayout()
                OverlayWidgetStore.seedFromLayout(layoutConfig)
                if (layoutConfig.enabled) {
                    if (!showOverlay()) {
                        ScriptLog.w("重新加载后无法显示浮动面板")
                    }
                    startStatusTracking()
                }
            }
            ACTION_STOP -> {
                removeOverlay()
                stopSelf()
            }
            else -> if (layoutConfig.enabled && panelView == null) {
                if (!showOverlay()) {
                    ScriptLog.w("无法显示浮动面板，请授予悬浮窗权限")
                }
                startStatusTracking()
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        ScriptStatus.removeRunningListener(scriptRunningListener)
        stopStatusTracking()
        handler.removeCallbacks(logFlushRunnable)
        flushPendingLog()
        cancelIdleCollapse()
        removeOverlay()
        snippetJob?.cancel()
        super.onDestroy()
    }

    private fun startStatusTracking() {
        if (statusPollActive) return
        statusPollActive = true
        handler.postDelayed(statusPollRunnable, 1500)
    }

    private fun stopStatusTracking() {
        handler.removeCallbacks(statusPollRunnable)
        statusPollActive = false
    }

    private fun installLogSink() {
        OverlayLog.sink = { msg -> queueLogLine(msg) }
    }

    private fun queueLogLine(msg: String) {
        synchronized(logPending) {
            logPending.append(msg).append('\n')
        }
        handler.removeCallbacks(logFlushRunnable)
        handler.postDelayed(logFlushRunnable, 100)
    }

    private fun flushPendingLog() {
        val chunk = synchronized(logPending) {
            if (logPending.isEmpty()) return
            val text = logPending.toString()
            logPending.clear()
            text
        }
        logView?.append(chunk)
    }

    private fun layoutModeReset() {
        designMode = false
        selectedWidgetPath = null
    }

    private fun loadLayout(): LayoutConfig {
        return runCatching {
            LayoutOverrideStore.load(this)
        }.getOrElse {
            ScriptLog.w("加载 layout.json 失败，使用默认布局")
            LayoutConfig.DEFAULT
        }
    }

    private fun screenWidthPx(): Int {
        val dm = resources.displayMetrics
        return dm.widthPixels.coerceAtLeast(1)
    }

    private fun screenHeightPx(): Int {
        val dm = resources.displayMetrics
        return dm.heightPixels.coerceAtLeast(1)
    }

    private fun applyPanelPosition(lp: WindowManager.LayoutParams, widthPx: Int, heightPx: Int) {
        val margin = dp(12)
        val screenW = screenWidthPx()
        val screenH = screenHeightPx()
        val h = heightPx.coerceAtLeast(dp(48))
        lp.gravity = Gravity.TOP or Gravity.START
        when (layoutConfig.panel.position.lowercase()) {
            "right_center", "right" -> {
                lp.x = (screenW - widthPx - margin - layoutConfig.panel.startX).coerceAtLeast(margin)
                lp.y = ((screenH - h) / 2f).toInt().coerceAtLeast(margin) + layoutConfig.panel.startY
            }
            "left_center", "left" -> {
                lp.x = (layoutConfig.panel.startX + margin).coerceAtLeast(margin)
                lp.y = ((screenH - h) / 2f).toInt().coerceAtLeast(margin) + layoutConfig.panel.startY
            }
            else -> {
                lp.x = layoutConfig.panel.startX
                lp.y = layoutConfig.panel.startY
            }
        }
    }

    private fun isMinimalDisplay(): Boolean =
        layoutConfig.isHostDisplay() ||
            layoutConfig.panel.displayMode.equals("minimal", ignoreCase = true) ||
            layoutConfig.resolvedScreens().any { it.widgets.isNotEmpty() }

    private fun scheduleIdleCollapse() {
        handler.removeCallbacks(idleCollapseRunnable)
        val idleMs = layoutConfig.panel.autoCollapseIdleMs
        if (idleMs <= 0 || collapsed || designMode || scriptRunning) return
        handler.postDelayed(idleCollapseRunnable, idleMs.toLong())
    }

    private fun bumpIdleTimer() {
        if (layoutConfig.panel.autoCollapseIdleMs <= 0 || collapsed || designMode) return
        scheduleIdleCollapse()
    }

    private fun cancelIdleCollapse() {
        handler.removeCallbacks(idleCollapseRunnable)
    }

    private fun onIdleCollapse() {
        if (collapsed || designMode || scriptRunning) return
        if (!layoutConfig.panel.collapsible) return
        forceCollapse()
        appendLog("无操作已自动收起到悬浮球")
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun showOverlay(): Boolean {
        if (panelView != null) return true
        if (!hasOverlayPermission()) {
            ScriptLog.w("无悬浮窗权限，无法显示浮动面板")
            return false
        }
        unifiedMinimalBar = isMinimalDisplay()
        if (unifiedMinimalBar && !restoreCollapsedAfterBuild) {
            collapsed = true
        }
        restoreCollapsedAfterBuild = false
        if (unifiedMinimalBar) {
            val ballSize = dp(layoutConfig.panel.ballSizeDp)
            panelWidthPx = ballSize
            panelHeightPx = ballSize
        } else {
            panelWidthPx = PanelWidthResolver.resolveWidthPx(
                layoutConfig.panel,
                screenWidthPx(),
                ::dp,
            )
            panelHeightPx = PanelHeightResolver.resolveHeightPx(
                layoutConfig.panel,
                screenHeightPx(),
                ::dp,
            )
        }
        val panel = buildPanel()
        val type = overlayWindowType()
        val focusable = layoutConfig.needsFocusablePanel() && !designMode && !unifiedMinimalBar
        val panelLp = WindowManager.LayoutParams(
            if (unifiedMinimalBar) panelWidthPx else panelWidthPx,
            if (unifiedMinimalBar) panelHeightPx ?: panelWidthPx
            else panelHeightPx ?: WindowManager.LayoutParams.WRAP_CONTENT,
            type,
            if (focusable) {
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
            } else {
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
            },
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = layoutConfig.panel.startX
            y = layoutConfig.panel.startY
            alpha = if (unifiedMinimalBar) 1f else layoutConfig.panel.opacity.coerceIn(0.2f, 1.0f)
        }
        val estH = panelHeightPx ?: if (unifiedMinimalBar) panelWidthPx else dp(200)
        applyPanelPosition(panelLp, panelWidthPx, estH)
        val ballLp = if (!unifiedMinimalBar) {
            WindowManager.LayoutParams(
                dp(layoutConfig.panel.ballSizeDp),
                dp(layoutConfig.panel.ballSizeDp),
                type,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
                PixelFormat.TRANSLUCENT,
            ).apply {
                gravity = Gravity.TOP or Gravity.END
                x = 24
                y = layoutConfig.panel.startY
            }
        } else {
            null
        }
        if (layoutConfig.panel.draggable && !designMode) {
            val dragTarget = if (focusable) titleDragHandle ?: panel else panel
            val onLongPress = if (
                layoutConfig.panel.allowDesign && dragTarget === titleDragHandle && !unifiedMinimalBar
            ) {
                ::toggleDesignMode
            } else {
                null
            }
            attachDrag(dragTarget, panelLp, onLongPress = onLongPress) { onMinimalDragTap() }
            if (!unifiedMinimalBar && ballLp != null) {
                val ball = buildBall()
                attachDrag(ball, ballLp) { onBallClicked() }
                if (!safeAddOverlayView(ball, ballLp)) return false
                ball.visibility = View.GONE
                ballView = ball
                ballParams = ballLp
            }
        } else if (!unifiedMinimalBar) {
            val ball = buildBall()
            if (!safeAddOverlayView(ball, ballLp!!)) return false
            ball.visibility = View.GONE
            ballView = ball
            ballParams = ballLp
        }
        if (!safeAddOverlayView(panel, panelLp)) return false
        panelView = panel
        layoutParams = panelLp
        if (!unifiedMinimalBar && ballView != null) {
            if (collapsed) {
                panel.visibility = View.GONE
                ballView?.visibility = View.VISIBLE
            }
        } else if (unifiedMinimalBar) {
            applyMinimalCollapseUi()
        }
        updateBallAppearance()
        if (!collapsed) scheduleIdleCollapse()
        return true
    }

    private fun overlayWindowType(): Int =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }

    private fun hasOverlayPermission(): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Settings.canDrawOverlays(this)
        } else {
            true
        }

    private fun safeAddOverlayView(view: View, lp: WindowManager.LayoutParams): Boolean {
        return try {
            wm.addView(view, lp)
            true
        } catch (e: Exception) {
            ScriptLog.w("浮动窗 addView 失败: ${e.message}")
            false
        }
    }

    private fun buildPanel(): View {
        if (isMinimalDisplay()) return buildMinimalFloatingBar()
        val theme = OverlayTheme.from(layoutConfig.panel.theme)
        val corner = dp(12).toFloat()
        val builder = OverlayPanelBuilder(
            context = this,
            theme = theme,
            onAction = ::onWidgetAction,
            dp = ::dp,
            designMode = designMode,
            designCallbacks = if (designMode) designCallbacks else null,
        )
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = theme.panelDrawable(corner)
            setPadding(dp(1), dp(1), dp(1), dp(8))
        }
        val titleWrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = theme.titleBarDrawable(corner)
            setPadding(dp(10), dp(8), dp(10), dp(8))
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            )
        }
        titleDragHandle = titleWrap
        val title = TextView(this).apply {
            text = layoutConfig.panel.title
            setTextColor(theme.titleText)
            textSize = 14f
            paint.isFakeBoldText = true
            gravity = Gravity.CENTER
            textAlignment = android.view.View.TEXT_ALIGNMENT_CENTER
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            )
        }
        titleWrap.addView(title)
        root.addView(titleWrap)

        if (designMode) {
            root.addView(buildDesignToolbar(theme))
        }

        val gridWrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(6), dp(6), dp(6), dp(4))
        }
        val cols = layoutConfig.panel.columns.coerceIn(1, 3)
        if (layoutConfig.isFreeMode() && layoutConfig.resolvedScreens().isNotEmpty()) {
            val screenPanel = OverlayScreenPanelBuilder(
                context = this,
                theme = theme,
                layoutConfig = layoutConfig,
                widgetBuilder = builder,
                dp = ::dp,
                panelWidthPx = panelWidthPx,
                onActiveScreenChange = { idx ->
                    layoutConfig = layoutConfig.copy(
                        panel = layoutConfig.panel.copy(activeScreen = idx),
                    )
                },
            ).build()
            gridWrap.addView(screenPanel)
        } else {
            val widgets = if (layoutConfig.screens.isNotEmpty()) {
                layoutConfig.resolvedScreens().flatMap { it.widgets } + layoutConfig.chromeWidgets()
            } else {
                layoutConfig.widgets
            }
            gridWrap.addView(builder.buildContentGrid(widgets, cols))
        }
        root.addView(gridWrap)
        if (layoutConfig.panel.showLog) {
            val scroll = ScrollView(this).apply {
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    dp(84),
                ).apply { setMargins(dp(8), 0, dp(8), dp(4)) }
                background = theme.logDrawable(dp(8).toFloat())
                setPadding(dp(8), dp(6), dp(8), dp(6))
            }
            logView = TextView(this).apply {
                setTextColor(theme.logText)
                textSize = 10f
                setLineSpacing(2f, 1f)
                text = ""
            }
            scroll.addView(logView)
            root.addView(scroll)
        }
        OverlayLog.replay { line -> queueLogLine(line) }
        installLogSink()
        return root
    }

    private fun buildMinimalFloatingBar(): View {
        val theme = OverlayTheme.from(layoutConfig.panel.theme)
        val ballSize = dp(layoutConfig.panel.ballSizeDp)
        val gap = dp(4)
        val showLog = layoutConfig.panel.showLog

        val outer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.TRANSPARENT)
            setPadding(0, 0, 0, 0)
        }
        titleDragHandle = outer

        val toolbar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setBackgroundColor(Color.TRANSPARENT)
        }
        minimalToolbarRow = toolbar

        val ballHost = FrameLayout(this).apply {
            layoutParams = LinearLayout.LayoutParams(ballSize, ballSize)
            isClickable = false
            isFocusable = false
            setBackgroundColor(Color.TRANSPARENT)
        }
        minimalBallHost = ballHost
        val iv = ImageView(this).apply {
            ballImageView = this
            scaleType = ImageView.ScaleType.FIT_CENTER
            adjustViewBounds = true
            isClickable = false
            isFocusable = false
            setBackgroundColor(Color.TRANSPARENT)
        }
        ballHost.addView(
            iv,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT,
            ),
        )
        val fallback = TextView(this).apply {
            ballFallbackView = this
            gravity = Gravity.CENTER
            textSize = 18f
            visibility = View.GONE
            setBackgroundColor(Color.TRANSPARENT)
            setTextColor(Color.WHITE)
            setShadowLayer(6f, 0f, 1f, Color.BLACK)
        }
        ballHost.addView(
            fallback,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT,
            ),
        )
        val badge = TextView(this).apply {
            ballBadgeView = this
            gravity = Gravity.CENTER
            textSize = 10f
            setTextColor(Color.WHITE)
            visibility = View.GONE
        }
        ballHost.addView(
            badge,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM or Gravity.END,
            ).apply { setMargins(0, 0, dp(2), dp(2)) },
        )
        loadBallImage()

        val chrome = minimalChromeControls()
        val controlsFrame = if (chrome.isNotEmpty()) {
            val frameW = chrome.maxOf { it.layoutX + it.layoutW }.coerceAtLeast(48)
            val frameH = chrome.maxOf { it.layoutY + it.layoutH }.coerceAtLeast(32)
            FrameLayout(this).apply {
                visibility = View.GONE
                setBackgroundColor(Color.TRANSPARENT)
                layoutParams = LinearLayout.LayoutParams(dp(frameW), dp(frameH))
            }.also { frame ->
                minimalControlsFrame = frame
                chrome.forEach { cfg ->
                    val (icon, color, action) = when (cfg.type) {
                        "stop_script" -> Triple("■", Color.parseColor("#EF4444")) { stopMainScript() }
                        else -> Triple("▶", Color.parseColor("#22C55E")) { onStartButtonPressed() }
                    }
                    placeMinimalControl(frame, cfg, icon, color, action)
                }
                minimalControlsWrap = frame
                toolbar.addView(frame)
            }
        } else {
            minimalControlsFrame = null
            minimalControlsWrap = null
            null
        }

        if (showLog) {
            val logBtnSize = dp(28)
            val logToggle = minimalIconButton("▤", Color.parseColor("#94A3B8")) { toggleMinimalLog() }.apply {
                textSize = 14f
                visibility = View.GONE
            }
            minimalLogToggle = logToggle
            toolbar.addView(
                logToggle,
                LinearLayout.LayoutParams(logBtnSize, logBtnSize).apply { marginStart = gap },
            )
        }

        toolbar.addView(
            ballHost,
            LinearLayout.LayoutParams(ballSize, ballSize).apply { marginStart = gap },
        )

        outer.addView(toolbar)

        if (showLog) {
            val logH = dp(layoutConfig.panel.logHeightDp.coerceIn(48, 200))
            val logWrap = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                visibility = View.GONE
                setPadding(dp(2), dp(4), dp(2), dp(2))
                background = theme.logDrawable(dp(8).toFloat()).apply {
                    alpha = 220
                }
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    logH,
                ).apply { topMargin = dp(4) }
                minimumWidth = dp(160)
            }
            minimalLogWrap = logWrap
            val scroll = ScrollView(this).apply {
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.MATCH_PARENT,
                )
                isVerticalScrollBarEnabled = true
            }
            logView = TextView(this).apply {
                setTextColor(theme.logText)
                textSize = 9f
                setLineSpacing(1f, 1f)
                text = ""
            }
            scroll.addView(logView)
            logWrap.addView(scroll)
            outer.addView(logWrap)
            OverlayLog.replay { line -> queueLogLine(line) }
        }

        installLogSink()
        return outer
    }

    private fun minimalChromeControls(): List<WidgetConfig> {
        // 主页面 host：启停由悬浮球承担，不再单独渲染开始/停止按钮
        if (layoutConfig.isHostDisplay()) return emptyList()
        val chrome = layoutConfig.chromeWidgets().filter {
            it.type == "start_script" || it.type == "stop_script"
        }
        val start = chrome.firstOrNull { it.type == "start_script" }
            ?: WidgetConfig(
                id = "start",
                type = "start_script",
                layoutX = 0,
                layoutY = 8,
                layoutW = 32,
                layoutH = 32,
            )
        val stop = chrome.firstOrNull { it.type == "stop_script" }
            ?: WidgetConfig(
                id = "stop",
                type = "stop_script",
                layoutX = 34,
                layoutY = 8,
                layoutW = 32,
                layoutH = 32,
            )
        return listOf(start, stop)
    }

    private fun placeMinimalControl(
        host: FrameLayout,
        cfg: WidgetConfig,
        icon: String,
        color: Int,
        onClick: () -> Unit,
    ) {
        val w = dp(cfg.layoutW.coerceIn(24, 44))
        val h = dp(cfg.layoutH.coerceIn(24, 44))
        val btn = minimalIconButton(icon, color, onClick).apply {
            textSize = cfg.layoutH.coerceIn(24, 44) * 0.38f
        }
        host.addView(
            btn,
            FrameLayout.LayoutParams(w, h).apply {
                leftMargin = dp(cfg.layoutX)
                topMargin = dp(cfg.layoutY)
            },
        )
    }

    private fun toggleMinimalLog() {
        if (!layoutConfig.panel.showLog || collapsed) return
        minimalLogExpanded = !minimalLogExpanded
        minimalLogWrap?.visibility = if (minimalLogExpanded) View.VISIBLE else View.GONE
        updateMinimalWindowSize()
        bumpIdleTimer()
    }

    private fun minimalIconButton(
        icon: String,
        color: Int,
        onClick: () -> Unit,
    ): TextView = TextView(this).apply {
        text = icon
        gravity = Gravity.CENTER
        textSize = 18f
        setTextColor(color)
        setBackgroundColor(Color.TRANSPARENT)
        setShadowLayer(6f, 0f, 1f, Color.BLACK)
        isClickable = true
        isFocusable = true
        setOnClickListener {
            bumpIdleTimer()
            onClick()
        }
    }

    /** 轻点悬浮条（非拖动）时切换展开/收起；host 模式下点击悬浮球启停脚本。 */
    private fun onMinimalDragTap() {
        if (!unifiedMinimalBar) return
        if (layoutConfig.isHostDisplay()) {
            onHostBallAction()
            return
        }
        onMinimalBallClick()
    }

    private fun onHostBallAction() {
        bumpIdleTimer()
        if (scriptRunning) {
            stopMainScript()
        } else {
            startMainScript()
        }
    }

    private fun onMinimalBallClick() {
        bumpIdleTimer()
        if (collapsed) {
            collapsed = false
            applyMinimalCollapseUi()
            scheduleIdleCollapse()
        } else {
            forceCollapse()
        }
    }

    private fun applyMinimalCollapseUi() {
        if (!unifiedMinimalBar) return
        val showControls = !collapsed && !layoutConfig.isHostDisplay()
        minimalControlsFrame?.visibility = if (showControls) View.VISIBLE else View.GONE
        minimalControlsWrap?.visibility = if (showControls) View.VISIBLE else View.GONE
        val showLogBtn = showControls && layoutConfig.panel.showLog
        minimalLogToggle?.visibility = if (showLogBtn) View.VISIBLE else View.GONE
        if (!showControls) {
            minimalLogWrap?.visibility = View.GONE
        } else {
            minimalLogWrap?.visibility =
                if (minimalLogExpanded && layoutConfig.panel.showLog) View.VISIBLE else View.GONE
        }
        updateMinimalWindowSize()
        updateBallAppearance()
    }

    private fun updateMinimalWindowSize() {
        if (!unifiedMinimalBar || panelView == null || layoutParams == null) return
        val lp = layoutParams ?: return
        val ballSize = dp(layoutConfig.panel.ballSizeDp)
        if (collapsed) {
            lp.width = ballSize
            lp.height = ballSize
        } else {
            lp.width = WindowManager.LayoutParams.WRAP_CONTENT
            lp.height = WindowManager.LayoutParams.WRAP_CONTENT
        }
        runCatching { wm.updateViewLayout(panelView, lp) }
    }

    private fun buildDesignToolbar(theme: OverlayTheme): LinearLayout =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(8), dp(4), dp(8), dp(4))
            setBackgroundColor(Color.parseColor("#EFF6FF"))
            addView(TextView(this@OverlayService).apply {
                text = "设计模式"
                setTextColor(theme.titleText)
                textSize = 12f
                paint.isFakeBoldText = true
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            })
            addView(Button(this@OverlayService).apply {
                text = "保存"
                textSize = 11f
                isAllCaps = false
                stateListAnimator = null
                elevation = 0f
                minHeight = dp(32)
                background = theme.buttonDrawable("#2563EB", dp(6).toFloat())
                setTextColor(theme.buttonTextColor("#2563EB"))
                setOnClickListener { saveDesignLayout() }
            })
            addView(Button(this@OverlayService).apply {
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
            })
        }

    @SuppressLint("ClickableViewAccessibility")
    private fun attachDrag(
        view: View,
        lp: WindowManager.LayoutParams,
        onLongPress: (() -> Unit)? = null,
        onClick: (() -> Unit)? = null,
    ) {
        var downX = 0f
        var downY = 0f
        var startX = 0
        var startY = 0
        var moved = false
        var longPressFired = false
        val longPressRunnable = Runnable {
            if (!moved) {
                longPressFired = true
                onLongPress?.invoke()
            }
        }
        view.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    downX = event.rawX
                    downY = event.rawY
                    startX = lp.x
                    startY = lp.y
                    moved = false
                    longPressFired = false
                    bumpIdleTimer()
                    if (onLongPress != null) handler.postDelayed(longPressRunnable, 1200)
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = (event.rawX - downX).toInt()
                    val dy = (event.rawY - downY).toInt()
                    if (abs(dx) > 5 || abs(dy) > 5) {
                        moved = true
                        handler.removeCallbacks(longPressRunnable)
                    }
                    if (moved && !longPressFired) {
                        lp.x = startX + dx
                        lp.y = startY + dy
                        val anchor = panelView ?: view
                        wm.updateViewLayout(anchor, lp)
                    }
                    true
                }
                MotionEvent.ACTION_UP -> {
                    handler.removeCallbacks(longPressRunnable)
                    if (!moved && !longPressFired) onClick?.invoke()
                    true
                }
                MotionEvent.ACTION_CANCEL -> {
                    handler.removeCallbacks(longPressRunnable)
                    true
                }
                else -> false
            }
        }
    }

    private fun toggleDesignMode() {
        if (!layoutConfig.panel.allowDesign) return
        designMode = !designMode
        if (!designMode) selectedWidgetPath = null
        rebuildPanel()
        appendLog(if (designMode) "已进入布局设计模式" else "已退出布局设计模式")
    }

    private fun exitDesignMode() {
        designMode = false
        selectedWidgetPath = null
        rebuildPanel()
        appendLog("已退出布局设计模式")
    }

    private fun saveDesignLayout() {
        val file = LayoutOverrideStore.save(this, layoutConfig)
        Toast.makeText(this, "布局已保存", Toast.LENGTH_SHORT).show()
        appendLog("布局已保存: ${file.absolutePath}")
    }

    private fun rebuildPanel() {
        if (!layoutConfig.enabled) return
        val wasCollapsed = collapsed
        val lp = layoutParams
        val savedX = lp?.x ?: layoutConfig.panel.startX
        val savedY = lp?.y ?: layoutConfig.panel.startY
        removeOverlay()
        collapsed = wasCollapsed
        restoreCollapsedAfterBuild = true
        layoutConfig = layoutConfig.copy(
            panel = layoutConfig.panel.copy(startX = savedX, startY = savedY),
        )
        showOverlay()
    }

    private fun buildBall(): View {
        return FrameLayout(this).apply {
            val iv = ImageView(context).apply {
                ballImageView = this
                scaleType = ImageView.ScaleType.FIT_CENTER
                adjustViewBounds = true
            }
            addView(
                iv,
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.MATCH_PARENT,
                ),
            )
            val fallback = TextView(context).apply {
                ballFallbackView = this
                gravity = Gravity.CENTER
                textSize = 13f
                visibility = View.GONE
            }
            addView(
                fallback,
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.MATCH_PARENT,
                ),
            )
            val badge = TextView(context).apply {
                ballBadgeView = this
                gravity = Gravity.CENTER
                textSize = 11f
                setTextColor(Color.WHITE)
                visibility = View.GONE
                setShadowLayer(4f, 0f, 1f, Color.BLACK)
            }
            addView(
                badge,
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.WRAP_CONTENT,
                    FrameLayout.LayoutParams.WRAP_CONTENT,
                    Gravity.BOTTOM or Gravity.END,
                ).apply {
                    setMargins(0, 0, dp(2), dp(2))
                },
            )
            loadBallImage()
            updateBallAppearance()
        }
    }

    private fun loadBallImage() {
        val iv = ballImageView ?: return
        val assets = ProjectAssets(this)
        if (!assets.exists("ui/ball.png")) {
            ballUsesImage = false
            return
        }
        runCatching {
            val bytes = assets.readBytes("ui/ball.png")
            val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
            if (bmp != null) {
                iv.setImageBitmap(bmp)
                ballUsesImage = true
            }
        }.onFailure {
            ScriptLog.w("加载悬浮球图标失败: ${it.message}")
            ballUsesImage = false
        }
    }

    private fun updateBallAppearance() {
        val theme = OverlayTheme.from(layoutConfig.panel.theme)
        val badge = ballBadgeView
        if (ballUsesImage) {
            val iv = ballImageView ?: return
            ballFallbackView?.visibility = View.GONE
            iv.visibility = View.VISIBLE
            if (unifiedMinimalBar) {
                when {
                    scriptRunning -> {
                        iv.setColorFilter(Color.parseColor("#EF4444"), PorterDuff.Mode.SRC_ATOP)
                        iv.imageAlpha = 235
                        badge?.apply {
                            text = "■"
                            visibility = View.VISIBLE
                        }
                    }
                    layoutConfig.isHostDisplay() -> {
                        iv.clearColorFilter()
                        iv.imageAlpha = if (startArmed) 255 else 200
                        badge?.apply {
                            text = "▶"
                            visibility = View.VISIBLE
                        }
                    }
                    else -> {
                        iv.clearColorFilter()
                        iv.imageAlpha = 255
                        badge?.visibility = View.GONE
                    }
                }
                return
            }
            when {
                scriptRunning -> {
                    iv.setColorFilter(Color.parseColor("#EF4444"), PorterDuff.Mode.SRC_ATOP)
                    iv.imageAlpha = 235
                    badge?.apply {
                        text = "■"
                        visibility = View.VISIBLE
                    }
                }
                startArmed -> {
                    iv.setColorFilter(Color.parseColor("#22C55E"), PorterDuff.Mode.SRC_ATOP)
                    iv.imageAlpha = 255
                    badge?.apply {
                        text = "▶"
                        visibility = View.VISIBLE
                    }
                }
                else -> {
                    iv.clearColorFilter()
                    iv.imageAlpha = 185
                    badge?.visibility = View.GONE
                }
            }
            return
        }
        val tv = ballFallbackView ?: return
        ivFallbackStyle(tv, theme)
    }

    private fun ivFallbackStyle(tv: TextView, theme: OverlayTheme) {
        ballImageView?.visibility = View.GONE
        tv.visibility = View.VISIBLE
        ballBadgeView?.visibility = View.GONE
        tv.background = null
        when {
            scriptRunning -> {
                tv.text = "■"
                tv.setTextColor(Color.parseColor("#EF4444"))
            }
            startArmed -> {
                tv.text = "▶"
                tv.setTextColor(Color.parseColor("#22C55E"))
            }
            else -> {
                tv.text = "▶"
                tv.setTextColor(Color.WHITE)
            }
        }
        tv.setShadowLayer(6f, 0f, 1f, Color.BLACK)
    }

    private fun onBallClicked() {
        if (scriptRunning) {
            stopMainScript()
            return
        }
        if (startArmed) {
            startArmed = false
            updateBallAppearance()
            startMainScript()
            return
        }
        toggleCollapse()
    }

    private fun onStartButtonPressed() {
        if (designMode) return
        if (isMinimalDisplay()) {
            startArmed = false
            updateBallAppearance()
            startMainScript()
            return
        }
        if (layoutConfig.panel.startConfirmCollapse && !collapsed) {
            startArmed = true
            forceCollapse()
            updateBallAppearance()
            appendLog("已收起为悬浮球，点击悬浮球开始运行")
            return
        }
        startArmed = false
        updateBallAppearance()
        startMainScript()
    }

    private fun forceCollapse() {
        if (!layoutConfig.panel.collapsible || collapsed) return
        collapsed = true
        cancelIdleCollapse()
        if (unifiedMinimalBar) {
            applyMinimalCollapseUi()
            return
        }
        panelView?.visibility = View.GONE
        ballView?.visibility = View.VISIBLE
    }

    private fun onWidgetAction(cfg: WidgetConfig) {
        bumpIdleTimer()
        appendLog("点击: ${cfg.label}")
        when (cfg.effectiveAction().lowercase()) {
            "start_script" -> onStartButtonPressed()
            "stop_script" -> stopMainScript()
            "collapse", "hide" -> toggleCollapse()
            "tap" -> runSnippet {
                val backend = automationBackend()
                backend.tap(cfg.x, cfg.y)
            }
            "long_press" -> runSnippet {
                val backend = automationBackend()
                backend.longPress(cfg.x, cfg.y, cfg.durationMs)
            }
            "swipe" -> runSnippet {
                val backend = automationBackend()
                backend.swipe(cfg.x1, cfg.y1, cfg.x2, cfg.y2, cfg.durationMs)
            }
            "lua", "snippet" -> runLuaSnippet(cfg.lua)
            "open_app" -> {
                val intent = packageManager.getLaunchIntentForPackage(packageName)
                intent?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                if (intent != null) startActivity(intent)
            }
            else -> appendLog("未知控件动作: ${cfg.effectiveAction()}")
        }
    }

    private fun startMainScript() {
        val intent = Intent(this, ScriptRunnerService::class.java).apply {
            action = ScriptRunnerService.ACTION_START
        }
        startForegroundService(intent)
        scriptRunning = true
        updateBallAppearance()
        if (layoutConfig.panel.collapsible && !collapsed) {
            forceCollapse()
        }
        appendLog("已启动主脚本")
    }

    private fun stopMainScript() {
        startArmed = false
        scriptRunning = false
        updateBallAppearance()
        ScriptCancelToken.cancel()
        val intent = Intent(this, ScriptRunnerService::class.java).apply {
            action = ScriptRunnerService.ACTION_STOP
        }
        startService(intent)
        appendLog("已请求停止脚本")
        if (collapsed && layoutConfig.panel.collapsible && !unifiedMinimalBar) {
            toggleCollapse()
        }
    }

    private fun runSnippet(block: suspend () -> Unit) {
        snippetJob?.cancel()
        snippetJob = scope.launch(Dispatchers.IO) {
            try {
                block()
            } catch (e: Exception) {
                appendLog("执行失败: ${e.message}")
            }
        }
    }

    private fun runLuaSnippet(lua: String) {
        if (lua.isBlank()) return
        snippetJob?.cancel()
        snippetJob = scope.launch(Dispatchers.IO) {
            try {
                val assets = ProjectAssets(this@OverlayService)
                LuaSnippetRunner.run(assets, automationBackend(), lua, ::appendLog)
            } catch (e: Exception) {
                appendLog("Lua 片段错误: ${e.message}")
            }
        }
    }

    private fun automationBackend(): com.autoscript.core.backend.AutomationBackend {
        val cfg = ProjectAssets(this).loadConfig()
        return DeviceAutomationBackend(cfg)
    }

    private fun toggleCollapse() {
        if (!layoutConfig.panel.collapsible) return
        collapsed = !collapsed
        if (unifiedMinimalBar) {
            applyMinimalCollapseUi()
            if (collapsed) cancelIdleCollapse() else scheduleIdleCollapse()
            return
        }
        panelView?.visibility = if (collapsed) View.GONE else View.VISIBLE
        ballView?.visibility = if (collapsed) View.VISIBLE else View.GONE
        if (collapsed) cancelIdleCollapse() else scheduleIdleCollapse()
    }

    private fun appendLog(msg: String) {
        ScriptLog.i(msg)
        MainActivity.logSink?.invoke(msg) ?: OverlayLog.notify(msg)
    }

    private fun removeOverlay() {
        panelView?.let { runCatching { wm.removeView(it) } }
        ballView?.let { runCatching { wm.removeView(it) } }
        panelView = null
        ballView = null
        ballImageView = null
        ballFallbackView = null
        ballBadgeView = null
        ballUsesImage = false
        unifiedMinimalBar = false
        minimalControlsWrap = null
        minimalControlsFrame = null
        minimalLogWrap = null
        minimalLogToggle = null
        minimalToolbarRow = null
        minimalLogExpanded = false
        minimalBallHost = null
        titleDragHandle = null
        layoutParams = null
        ballParams = null
        cancelIdleCollapse()
        OverlayLog.sink = null
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    private fun buildNotification(text: String): Notification {
        val channelId = "auto_script_overlay"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = getSystemService(NotificationManager::class.java)
            mgr.createNotificationChannel(
                NotificationChannel(channelId, "浮动面板", NotificationManager.IMPORTANCE_LOW),
            )
        }
        return NotificationCompat.Builder(this, channelId)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_launcher)
            .setOngoing(true)
            .build()
    }

    companion object {
        const val ACTION_TOGGLE = "com.autoscript.overlay.TOGGLE"
        const val ACTION_RELOAD = "com.autoscript.overlay.RELOAD"
        const val ACTION_STOP = "com.autoscript.overlay.STOP"
        private const val NOTIFICATION_ID = 1002

        fun start(context: android.content.Context) {
            val intent = Intent(context, OverlayService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: android.content.Context) {
            val intent = Intent(context, OverlayService::class.java).apply { action = ACTION_STOP }
            context.startService(intent)
        }
    }
}

/** 浮动面板日志桥接（与主界面运行日志共用脚本输出） */
object OverlayLog {
    private const val MAX_LINES = 256
    private val buffer = ArrayDeque<String>(MAX_LINES)
    private val lock = Any()

    @Volatile
    var sink: ((String) -> Unit)? = null

    fun notify(msg: String) {
        appendToBuffer(msg)
        sink?.invoke(msg)
    }

    fun appendToBuffer(msg: String) {
        synchronized(lock) {
            if (buffer.size >= MAX_LINES) buffer.removeFirst()
            buffer.addLast(msg)
        }
    }

    fun replay(to: (String) -> Unit) {
        synchronized(lock) {
            buffer.forEach { to(it) }
        }
    }
}
