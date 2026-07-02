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
import com.autoscript.core.overlay.OverlayTheme
import com.autoscript.core.overlay.OverlayWidgetStore
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
    private var layoutConfig: LayoutConfig = LayoutConfig.DEFAULT
    private var designMode = false
    private var selectedWidgetPath: List<Int>? = null
    private val scope = CoroutineScope(Dispatchers.Main)
    private var snippetJob: Job? = null
    private val handler = Handler(Looper.getMainLooper())
    private val statusPollRunnable = object : Runnable {
        override fun run() {
            val running = ScriptStatus.isRunning(this@OverlayService)
            if (running != scriptRunning) {
                scriptRunning = running
                updateBallAppearance()
            }
            handler.postDelayed(this, 500)
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
        if (layoutConfig.enabled) {
            showOverlay()
            handler.post(statusPollRunnable)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_TOGGLE -> toggleCollapse()
            ACTION_RELOAD -> {
                removeOverlay()
                layoutModeReset()
                layoutConfig = loadLayout()
                OverlayWidgetStore.seedFromLayout(layoutConfig)
                if (layoutConfig.enabled) showOverlay()
            }
            ACTION_STOP -> {
                removeOverlay()
                stopSelf()
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        handler.removeCallbacks(statusPollRunnable)
        removeOverlay()
        snippetJob?.cancel()
        super.onDestroy()
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

    @SuppressLint("ClickableViewAccessibility")
    private fun showOverlay() {
        if (panelView != null) return
        val panel = buildPanel()
        val ball = buildBall()
        val type = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        val focusable = layoutConfig.needsFocusablePanel() && !designMode
        val panelLp = WindowManager.LayoutParams(
            dp(layoutConfig.panel.widthDp),
            WindowManager.LayoutParams.WRAP_CONTENT,
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
            alpha = layoutConfig.panel.opacity.coerceIn(0.2f, 1.0f)
        }
        val ballLp = WindowManager.LayoutParams(
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
        if (layoutConfig.panel.draggable && !designMode) {
            val dragTarget = if (focusable) titleDragHandle ?: panel else panel
            val onLongPress = if (layoutConfig.panel.allowDesign && dragTarget === titleDragHandle) {
                ::toggleDesignMode
            } else {
                null
            }
            attachDrag(dragTarget, panelLp, onLongPress = onLongPress)
            attachDrag(ball, ballLp) { onBallClicked() }
        }
        wm.addView(panel, panelLp)
        wm.addView(ball, ballLp)
        ball.visibility = View.GONE
        panelView = panel
        ballView = ball
        layoutParams = panelLp
        ballParams = ballLp
        if (collapsed) {
            panel.visibility = View.GONE
            ball.visibility = View.VISIBLE
        }
        updateBallAppearance()
    }

    private fun buildPanel(): View {
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
        OverlayLog.sink = { msg -> handler.post { appendLog(msg) } }
        return root
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
        onClick: (() -> Unit)? = null,
        onLongPress: (() -> Unit)? = null,
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
                        wm.updateViewLayout(view, lp)
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
        layoutConfig = layoutConfig.copy(
            panel = layoutConfig.panel.copy(startX = savedX, startY = savedY),
        )
        showOverlay()
        collapsed = wasCollapsed
        if (wasCollapsed) {
            panelView?.visibility = View.GONE
            ballView?.visibility = View.VISIBLE
        }
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
        when {
            scriptRunning -> {
                tv.text = "■"
                tv.setTextColor(Color.WHITE)
                tv.background = theme.ballStopDrawable()
            }
            startArmed -> {
                tv.text = "▶"
                tv.setTextColor(Color.WHITE)
                tv.background = theme.ballArmedDrawable()
            }
            else -> {
                tv.text = "▶"
                tv.setTextColor(theme.ballText)
                tv.background = theme.ballDrawable()
            }
        }
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
        panelView?.visibility = View.GONE
        ballView?.visibility = View.VISIBLE
    }

    private fun onWidgetAction(cfg: WidgetConfig) {
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
        if (collapsed && layoutConfig.panel.collapsible) {
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
        panelView?.visibility = if (collapsed) View.GONE else View.VISIBLE
        ballView?.visibility = if (collapsed) View.VISIBLE else View.GONE
    }

    private fun appendLog(msg: String) {
        ScriptLog.i(msg)
        logView?.append("$msg\n")
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
        titleDragHandle = null
        layoutParams = null
        ballParams = null
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

/** 浮动面板日志桥接 */
object OverlayLog {
    @Volatile
    var sink: ((String) -> Unit)? = null
}
