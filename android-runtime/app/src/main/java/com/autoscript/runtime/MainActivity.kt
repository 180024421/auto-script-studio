package com.autoscript.runtime

import android.app.TimePickerDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.text.Editable
import android.text.TextWatcher
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SwitchCompat
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.autoscript.core.accessibility.AutomationAccessibilityService
import com.autoscript.core.backend.DeviceAutomationBackend
import com.autoscript.core.capture.CaptureSession
import com.autoscript.core.capture.ScreenCaptureManager
import com.autoscript.core.log.ScriptLog
import com.autoscript.core.license.LicenseStore
import com.autoscript.core.license.LicenseVerifier
import com.autoscript.core.overlay.LayoutConfig
import com.autoscript.core.overlay.LayoutOverrideStore
import com.autoscript.core.overlay.OverlayWidgetStore
import com.autoscript.core.overlay.PanelReloadDispatcher
import com.autoscript.core.overlay.PanelWidgetPreferences
import com.autoscript.core.project.ProjectAssets
import com.autoscript.core.project.SchedulePreferences
import com.autoscript.core.project.WifiLeavePreferences
import com.autoscript.core.root.RootShell
import com.autoscript.core.root.ShizukuInputBackend
import com.autoscript.core.update.UpdateNetwork
import com.autoscript.core.update.UpdatePreferences
import com.autoscript.core.update.UpdateServer
import com.autoscript.runtime.shizuku.ShizukuShell
import org.json.JSONObject
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var capture: ScreenCaptureManager
    private lateinit var statusText: TextView
    private lateinit var logText: TextView
    private lateinit var switchScheduleEnabled: SwitchCompat
    private lateinit var btnPickScheduleTime: Button
    private lateinit var switchWifiLeaveEnabled: SwitchCompat
    private lateinit var editCompanyWifiSsid: EditText
    private lateinit var btnUseCurrentWifi: Button
    private lateinit var btnPickWifiEarliest: Button
    private var scheduleHour = 8
    private var scheduleMinute = 55
    private var wifiEarliestHour = 17
    private var wifiEarliestMinute = 30
    private var pendingEnableWifiLeave = false
    private var autoRun = false
    private var autoRunTriggered = false
    private var autoRunAttempts = 0
    private var captureRequested = false
    private var updateDialogShown = false
    private var updateCheckRunning = false
    private var layoutConfig: LayoutConfig = LayoutConfig.DEFAULT
    private var hostPanelEnabled = false
    private var hostPanelRenderer: HostPanelRenderer? = null
    private val handler = Handler(Looper.getMainLooper())
    private val remindLayoutListener: (String, String) -> Unit = { id, _ ->
        if (id in setOf("remind_on", "wifi_leave_on", "work_hours", "company_wifi")) {
            syncRemindPrefsFromLayout()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        capture = ScreenCaptureManager(this)
        CaptureSession.bind(capture)

        runCatching {
            val cfg = ProjectAssets(this).loadConfig()
            autoRun = cfg.autoRun
            CaptureSession.useA11yScreenshot = cfg.screenshotMode == "accessibility"
            if (CaptureSession.useA11yScreenshot && CaptureSession.isA11yScreenshotAvailable()) {
                ScriptLog.i("screenshot_mode=accessibility（免录屏）")
            }
            RootShell.isAvailable()
            findViewById<TextView>(R.id.titleText)?.text = cfg.name.ifBlank { "Auto Script" }
        }

        statusText = findViewById(R.id.statusText)
        logText = findViewById(R.id.logText)
        switchScheduleEnabled = findViewById(R.id.switchScheduleEnabled)
        btnPickScheduleTime = findViewById(R.id.btnPickScheduleTime)
        switchWifiLeaveEnabled = findViewById(R.id.switchWifiLeaveEnabled)
        editCompanyWifiSsid = findViewById(R.id.editCompanyWifiSsid)
        btnUseCurrentWifi = findViewById(R.id.btnUseCurrentWifi)
        btnPickWifiEarliest = findViewById(R.id.btnPickWifiEarliest)

        layoutConfig = loadLayoutConfig()
        attachPanelStore(layoutConfig)
        OverlayWidgetStore.addChangeListener(remindLayoutListener)
        setupHostPanel()
        setupScheduleUi()
        setupWifiLeaveUi()

        findViewById<ImageButton>(R.id.btnSettings).setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
        findViewById<Button>(R.id.btnStart).setOnClickListener { startScript() }
        findViewById<Button>(R.id.btnStop).setOnClickListener { stopScript() }
        findViewById<Button>(R.id.btnOverlay).setOnClickListener { requestOverlayAndStart() }

        ShizukuShell.init()

        runCatching {
            ScheduleReceiver.scheduleNext(this)
        }
        WifiLeaveMonitorService.sync(this)
        maybeRequestNotificationPermission()

        appendLog("工程: ${runCatching { ProjectAssets(this).loadConfig().name }.getOrElse { "未打包" }}")
        runCatching {
            val (ver, name) = ProjectAssets(this).overlayVersionInfo()
            appendLog("脚本版本: v$ver${if (name.isNotBlank()) " ($name)" else ""}")
        }
        if (UpdateServer.isConfigured()) {
            appendLog("更新服务器: ${UpdateServer.apiBase()}")
        }
        logSink = { msg -> runOnUiThread { appendLog(msg) } }
    }

    private fun setupScheduleUi() {
        val cfg = runCatching { ProjectAssets(this).loadConfig() }.getOrNull()
        if (cfg == null) {
            findViewById<LinearLayout>(R.id.scheduleCard)?.visibility = android.view.View.GONE
            return
        }
        val enabled = SchedulePreferences.effectiveEnabled(this, cfg.schedule)
        val time = SchedulePreferences.effectiveDailyTime(this, cfg.schedule).ifBlank { "08:55" }
        parseScheduleTime(time)
        switchScheduleEnabled.setOnCheckedChangeListener(null)
        switchScheduleEnabled.isChecked = enabled
        btnPickScheduleTime.text = formatScheduleTime()
        switchScheduleEnabled.setOnCheckedChangeListener { _, isChecked ->
            persistAndReschedule(isChecked)
        }
        btnPickScheduleTime.setOnClickListener {
            TimePickerDialog(
                this,
                { _, hour, minute ->
                    scheduleHour = hour
                    scheduleMinute = minute
                    btnPickScheduleTime.text = formatScheduleTime()
                    persistAndReschedule(switchScheduleEnabled.isChecked)
                },
                scheduleHour,
                scheduleMinute,
                true,
            ).show()
        }
    }

    private fun parseScheduleTime(raw: String) {
        val parts = raw.split(":")
        scheduleHour = parts.getOrNull(0)?.toIntOrNull()?.coerceIn(0, 23) ?: 8
        scheduleMinute = parts.getOrNull(1)?.toIntOrNull()?.coerceIn(0, 59) ?: 55
    }

    private fun formatScheduleTime(): String =
        String.format(Locale.US, "%02d:%02d", scheduleHour, scheduleMinute)

    private fun persistAndReschedule(enabled: Boolean) {
        SchedulePreferences.save(this, enabled, formatScheduleTime())
        ScheduleReceiver.scheduleNext(this)
        appendLog(
            if (enabled) "已设置每日 ${formatScheduleTime()} 提醒"
            else "已关闭每日定时提醒",
        )
        refreshStatus()
    }

    private fun setupWifiLeaveUi() {
        switchWifiLeaveEnabled.setOnCheckedChangeListener(null)
        switchWifiLeaveEnabled.isChecked = WifiLeavePreferences.isEnabled(this)
        editCompanyWifiSsid.setText(WifiLeavePreferences.ssid(this))
        parseWifiEarliest(WifiLeavePreferences.earliestTime(this))
        btnPickWifiEarliest.text = formatWifiEarliest()

        switchWifiLeaveEnabled.setOnCheckedChangeListener { _, isChecked ->
            if (isChecked) {
                if (!hasLocationPermission()) {
                    pendingEnableWifiLeave = true
                    switchWifiLeaveEnabled.setOnCheckedChangeListener(null)
                    switchWifiLeaveEnabled.isChecked = false
                    switchWifiLeaveEnabled.setOnCheckedChangeListener { _, checked ->
                        onWifiLeaveEnabledChanged(checked)
                    }
                    requestLocationPermission()
                    appendLog("读取公司 WiFi 名需要定位权限，请先授权")
                    return@setOnCheckedChangeListener
                }
            }
            onWifiLeaveEnabledChanged(isChecked)
        }
        btnUseCurrentWifi.setOnClickListener {
            if (!hasLocationPermission()) {
                pendingEnableWifiLeave = false
                requestLocationPermission()
                appendLog("请先授权定位，再填入当前 WiFi")
                return@setOnClickListener
            }
            val ssid = WifiLeavePreferences.currentConnectedSsid(this)
            if (ssid.isNullOrBlank()) {
                appendLog("未读到当前 WiFi，请确认已连网且系统定位开关已开启")
                return@setOnClickListener
            }
            editCompanyWifiSsid.setText(ssid)
            WifiLeavePreferences.setSsid(this, ssid)
            appendLog("已填入当前 WiFi：$ssid")
            WifiLeaveMonitorService.sync(this)
        }
        btnPickWifiEarliest.setOnClickListener {
            TimePickerDialog(
                this,
                { _, hour, minute ->
                    wifiEarliestHour = hour
                    wifiEarliestMinute = minute
                    btnPickWifiEarliest.text = formatWifiEarliest()
                    WifiLeavePreferences.setEarliestTime(this, formatWifiEarliest())
                    appendLog("下班最早提醒设为 ${formatWifiEarliest()}")
                    WifiLeaveMonitorService.sync(this)
                },
                wifiEarliestHour,
                wifiEarliestMinute,
                true,
            ).show()
        }
        editCompanyWifiSsid.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
            override fun afterTextChanged(s: Editable?) {
                val ssid = s?.toString()?.trim().orEmpty()
                if (ssid.isNotEmpty()) {
                    WifiLeavePreferences.setSsid(this@MainActivity, ssid)
                }
            }
        })
    }

    private fun onWifiLeaveEnabledChanged(enabled: Boolean) {
        WifiLeavePreferences.setEnabled(this, enabled)
        val ssid = editCompanyWifiSsid.text?.toString()?.trim().orEmpty()
            .ifEmpty { WifiLeavePreferences.DEFAULT_SSID }
        WifiLeavePreferences.setSsid(this, ssid)
        WifiLeavePreferences.setEarliestTime(this, formatWifiEarliest())
        WifiLeaveMonitorService.sync(this)
        appendLog(
            if (enabled) "已启用离开 WiFi「$ssid」提醒（${formatWifiEarliest()} 后）"
            else "已关闭 WiFi 离开提醒",
        )
        refreshStatus()
    }

    private fun parseWifiEarliest(raw: String) {
        val parts = raw.split(":")
        wifiEarliestHour = parts.getOrNull(0)?.toIntOrNull()?.coerceIn(0, 23) ?: 17
        wifiEarliestMinute = parts.getOrNull(1)?.toIntOrNull()?.coerceIn(0, 59) ?: 30
    }

    private fun formatWifiEarliest(): String =
        String.format(Locale.US, "%02d:%02d", wifiEarliestHour, wifiEarliestMinute)

    private fun hasLocationPermission(): Boolean {
        val fine = ContextCompat.checkSelfPermission(
            this,
            android.Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        val coarse = ContextCompat.checkSelfPermission(
            this,
            android.Manifest.permission.ACCESS_COARSE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        return fine || coarse
    }

    private fun requestLocationPermission() {
        ActivityCompat.requestPermissions(
            this,
            arrayOf(
                android.Manifest.permission.ACCESS_FINE_LOCATION,
                android.Manifest.permission.ACCESS_COARSE_LOCATION,
            ),
            REQ_LOCATION,
        )
    }

    private fun maybeRequestNotificationPermission() {
        if (Build.VERSION.SDK_INT < 33) return
        if (ContextCompat.checkSelfPermission(
                this,
                android.Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        ActivityCompat.requestPermissions(
            this,
            arrayOf(android.Manifest.permission.POST_NOTIFICATIONS),
            REQ_NOTIFICATIONS,
        )
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_LOCATION) {
            if (hasLocationPermission()) {
                appendLog("定位已授权，可读取公司 WiFi 名称")
                if (pendingEnableWifiLeave) {
                    pendingEnableWifiLeave = false
                    switchWifiLeaveEnabled.setOnCheckedChangeListener(null)
                    switchWifiLeaveEnabled.isChecked = true
                    switchWifiLeaveEnabled.setOnCheckedChangeListener { _, checked ->
                        onWifiLeaveEnabledChanged(checked)
                    }
                    onWifiLeaveEnabledChanged(true)
                }
            } else {
                pendingEnableWifiLeave = false
                appendLog("未授权定位，无法根据 WiFi 判断离开公司")
            }
        }
    }

    private fun loadLayoutConfig(): LayoutConfig {
        val result = runCatching { LayoutOverrideStore.loadWithMeta(this) }
            .getOrElse {
                ScriptLog.w("加载 layout.json 失败，使用内置默认布局")
                return LayoutConfig.DEFAULT
            }
        when (result.source) {
            LayoutOverrideStore.LoadSource.APK_MISSING ->
                appendLog("警告: 未加载工程 ui/layout.json，当前为内置默认界面。请在 Studio 保存布局后「打包并安装」。")
            LayoutOverrideStore.LoadSource.USER_OVERRIDE ->
                appendLog("提示: 当前使用设备端设计模式保存的界面覆盖。")
            LayoutOverrideStore.LoadSource.APK -> Unit
        }
        return result.config
    }

    private fun attachPanelStore(layout: LayoutConfig) {
        val projectId = runCatching { ProjectAssets(this).loadConfig().packageId }.getOrDefault("default")
        PanelWidgetPreferences.attach(this, projectId, layout)
    }

    private fun reloadLayoutUi() {
        layoutConfig = loadLayoutConfig()
        attachPanelStore(layoutConfig)
        setupHostPanel()
        startService(Intent(this, OverlayService::class.java).apply {
            action = OverlayService.ACTION_RELOAD
        })
    }

    private fun setupHostPanel() {
        val container = findViewById<FrameLayout>(R.id.hostPanelContainer)
        val hostTitle = findViewById<TextView>(R.id.hostPanelTitle)
        val legacy = findViewById<LinearLayout>(R.id.legacyControlSection)
        val overlayBtn = findViewById<Button>(R.id.btnOverlay)
        val titleBlock = findViewById<LinearLayout>(R.id.appTitleBlock)
        val statusCard = findViewById<LinearLayout>(R.id.statusCard)
        hostPanelEnabled = layoutConfig.enabled &&
            layoutConfig.resolvedScreens().any { it.widgets.isNotEmpty() }
        if (!hostPanelEnabled) {
            hostPanelRenderer = null
            container.visibility = android.view.View.GONE
            hostTitle.visibility = android.view.View.GONE
            titleBlock.visibility = android.view.View.VISIBLE
            statusCard.visibility = android.view.View.VISIBLE
            findViewById<LinearLayout>(R.id.scheduleCard)?.visibility = android.view.View.VISIBLE
            findViewById<LinearLayout>(R.id.wifiLeaveCard)?.visibility = android.view.View.VISIBLE
            legacy.visibility = android.view.View.VISIBLE
            overlayBtn.visibility = android.view.View.VISIBLE
            return
        }
        titleBlock.visibility = android.view.View.GONE
        statusCard.visibility = android.view.View.GONE
        hostTitle.visibility = android.view.View.GONE
        // 配置已在 layout 表单中时隐藏原生提醒卡片，避免双份 UI
        val hideNativeRemind = layoutConfig.resolvedScreens().any { sc ->
            sc.widgets.any { it.id in setOf("remind_on", "work_hours", "company_wifi", "wifi_leave_on") }
        }
        findViewById<LinearLayout>(R.id.scheduleCard)?.visibility =
            if (hideNativeRemind) android.view.View.GONE else android.view.View.VISIBLE
        findViewById<LinearLayout>(R.id.wifiLeaveCard)?.visibility =
            if (hideNativeRemind) android.view.View.GONE else android.view.View.VISIBLE
        legacy.visibility = android.view.View.VISIBLE
        container.visibility = android.view.View.VISIBLE
        overlayBtn.visibility = android.view.View.GONE
        val keepDesign = hostPanelRenderer?.isDesignMode() == true
        container.post {
            val panelWidth = (container.width - container.paddingLeft - container.paddingRight)
                .coerceAtLeast(resources.displayMetrics.widthPixels - dp(40))
            val renderer = HostPanelRenderer(
                context = this,
                layoutConfig = layoutConfig,
                dp = ::dp,
                panelWidthPx = panelWidth,
                onActiveScreenChange = { idx ->
                    layoutConfig = layoutConfig.copy(
                        panel = layoutConfig.panel.copy(activeScreen = idx),
                    )
                },
                onLayoutChanged = { cfg ->
                    layoutConfig = cfg
                },
                onLog = { msg -> appendLog(msg) },
            )
            renderer.onRequestRebuild = {
                layoutConfig = renderer.currentLayout()
                setupHostPanel()
            }
            if (keepDesign) {
                renderer.forceDesignMode(true)
            }
            hostPanelRenderer = renderer
            container.removeAllViews()
            container.addView(renderer.build())
            syncRemindPrefsFromLayout()
        }
    }

    /** 从 layout 控件 id 同步上下班提醒偏好（钉钉提醒工程）。 */
    private fun syncRemindPrefsFromLayout() {
        val all = layoutConfig.resolvedScreens().flatMap { it.widgets }
        if (all.none { it.id in setOf("remind_on", "wifi_leave_on", "work_hours", "company_wifi") }) {
            return
        }
        fun valOf(id: String, fallback: String = ""): String {
            val live = OverlayWidgetStore.get(id)
            if (live.isNotBlank()) return live
            val w = all.find { it.id == id } ?: return fallback
            return when (id) {
                "work_hours" -> {
                    val s = w.defaultStart.ifBlank { "08:55" }
                    val e = w.defaultEnd.ifBlank { "17:30" }
                    "$s-$e"
                }
                else -> w.default.ifBlank { fallback }
            }
        }
        fun asOn(raw: String): Boolean =
            raw.equals("true", ignoreCase = true) || raw == "1" || raw.equals("on", ignoreCase = true)

        val remindOn = asOn(valOf("remind_on", "true"))
        val hours = valOf("work_hours", "08:55-17:30")
        val start = hours.split("-").getOrNull(0)?.trim()?.ifBlank { "08:55" } ?: "08:55"
        val end = hours.split("-").getOrNull(1)?.trim()?.ifBlank { "17:30" } ?: "17:30"
        SchedulePreferences.save(this, remindOn, start)
        ScheduleReceiver.scheduleNext(this)

        val wifiRaw = valOf("wifi_leave_on", "")
        val wifiOn = if (wifiRaw.isNotBlank()) asOn(wifiRaw) else remindOn
        WifiLeavePreferences.setEnabled(this, wifiOn)
        val ssid = valOf("company_wifi", WifiLeavePreferences.DEFAULT_SSID)
        if (ssid.isNotBlank()) WifiLeavePreferences.setSsid(this, ssid)
        WifiLeavePreferences.setEarliestTime(this, end)
        WifiLeaveMonitorService.sync(this)
    }

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    override fun onDestroy() {
        OverlayWidgetStore.removeChangeListener(remindLayoutListener)
        handler.removeCallbacksAndMessages(null)
        if (logSink != null) logSink = null
        ShizukuShell.unbind()
        super.onDestroy()
    }

    override fun onResume() {
        super.onResume()
        val latest = loadLayoutConfig()
        if (latest != layoutConfig) {
            layoutConfig = latest
            attachPanelStore(layoutConfig)
            setupHostPanel()
        }
        refreshStatus()
        scheduleAutoRun()
        scheduleBuiltinUpdateCheck()
    }

    private fun requestOverlayAndStart() {
        if (Settings.canDrawOverlays(this)) {
            OverlayService.start(this)
            appendLog("悬浮控制已启动（开始/停止）")
            return
        }
        AlertDialog.Builder(this)
            .setTitle("悬浮窗权限")
            .setMessage("按键精灵式浮动面板需要「显示在其他应用上层」权限。可在右上角设置中授权。")
            .setPositiveButton("去设置") { _, _ ->
                startActivity(
                    Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:$packageName"),
                    ),
                )
            }
            .setNeutralButton("打开设置页") { _, _ ->
                startActivity(Intent(this, SettingsActivity::class.java))
            }
            .setNegativeButton("取消", null)
            .show()
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == ScreenCaptureManager.REQUEST_MEDIA_PROJECTION) {
            if (ScreenCaptureManager.handleActivityResult(capture, resultCode, data)) {
                appendLog("屏幕录制已授权")
            } else {
                appendLog("屏幕录制授权被拒绝")
                AlertDialog.Builder(this)
                    .setTitle("需要屏幕录制")
                    .setMessage("找图/识字/YOLO 需要屏幕录制权限。可在设置中授权，或使用无障碍截图模式。")
                    .setPositiveButton("打开设置") { _, _ ->
                        startActivity(Intent(this, SettingsActivity::class.java))
                    }
                    .setNegativeButton("取消", null)
                    .show()
            }
            refreshStatus()
            scheduleAutoRun()
        }
    }

    private fun automationBackend(): DeviceAutomationBackend {
        val cfg = ProjectAssets(this).loadConfig()
        return DeviceAutomationBackend(cfg)
    }

    private fun scheduleAutoRun() {
        if (!autoRun || autoRunTriggered) return
        handler.removeCallbacksAndMessages(null)
        handler.postDelayed({ maybeAutoRun() }, 1_500)
    }

    private fun maybeAutoRun() {
        if (!autoRun || autoRunTriggered) return
        val backend = automationBackend()
        if (backend.needsAccessibility() && !AutomationAccessibilityService.isConnected()) {
            retryAutoRunLater()
            return
        }
        if (!CaptureSession.isActive() && backend.needsMediaProjection() && !captureRequested) {
            captureRequested = true
            appendLog("auto_run: 请求屏幕录制授权…")
            startActivityForResult(capture.createCaptureIntent(), ScreenCaptureManager.REQUEST_MEDIA_PROJECTION)
            retryAutoRunLater()
            return
        }
        if (!backend.isReady()) {
            retryAutoRunLater()
            return
        }
        autoRunTriggered = true
        appendLog(if (backend.usingRoot()) "auto_run: root 就绪，启动脚本" else "auto_run: 自动启动脚本")
        startScript()
    }

    private fun retryAutoRunLater() {
        autoRunAttempts++
        if (autoRunAttempts <= 25) {
            handler.postDelayed({ maybeAutoRun() }, 1_500)
        } else {
            appendLog("auto_run: 等待就绪超时（请在右上角设置中完成授权）")
        }
    }

    private fun startScript() {
        val cfg = ProjectAssets(this).loadConfig()
        val verifier = LicenseVerifier(this, cfg.license, cfg.packageId)
        if (cfg.license.enabled && !verifier.isLicensed()) {
            promptLicense { startScriptInternal() }
            return
        }
        startScriptInternal()
    }

    private fun promptLicense(onSuccess: (() -> Unit)? = null) {
        val input = android.widget.EditText(this)
        input.hint = "请输入卡密"
        LicenseStore.getCode(this)?.let { input.setText(it) }
        AlertDialog.Builder(this)
            .setTitle("卡密验证")
            .setMessage("本脚本需验证卡密后运行。也可在右上角设置中验证。")
            .setView(input)
            .setPositiveButton("验证") { _, _ ->
                val code = input.text?.toString()?.trim().orEmpty()
                val cfg = ProjectAssets(this).loadConfig()
                val verifier = LicenseVerifier(this, cfg.license, cfg.packageId)
                if (verifier.verifyAndBind(code)) {
                    appendLog("卡密验证成功")
                    onSuccess?.invoke()
                } else {
                    appendLog("卡密无效或网络错误")
                }
            }
            .setNeutralButton("打开设置") { _, _ ->
                startActivity(Intent(this, SettingsActivity::class.java))
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun startScriptInternal() {
        val backend = automationBackend()
        if (!backend.isReady()) {
            when {
                backend.usingRoot() && !RootShell.isAvailable() ->
                    appendLog("root 模式：请在设置中允许 su 权限")
                backend.needsAccessibility() && !AutomationAccessibilityService.isConnected() ->
                    appendLog("请先在设置中开启无障碍服务")
                backend.needsMediaProjection() && !CaptureSession.isActive() ->
                    appendLog("请先在设置中授权屏幕录制")
                else -> appendLog("环境未就绪，请打开右上角设置")
            }
            return
        }
        val intent = Intent(this, ScriptRunnerService::class.java)
        intent.action = ScriptRunnerService.ACTION_START
        startForegroundService(intent)
        findViewById<Button>(R.id.btnStart).isEnabled = false
        findViewById<Button>(R.id.btnStop).isEnabled = true
        appendLog("启动脚本…")
    }

    private fun stopScript() {
        val intent = Intent(this, ScriptRunnerService::class.java)
        intent.action = ScriptRunnerService.ACTION_STOP
        startService(intent)
        findViewById<Button>(R.id.btnStart).isEnabled = true
        findViewById<Button>(R.id.btnStop).isEnabled = false
        appendLog("已请求停止")
    }

    private fun scheduleBuiltinUpdateCheck() {
        if (updateCheckRunning || !UpdateServer.isConfigured()) return
        if (!UpdatePreferences.isCheckEnabled(this)) return
        if (!UpdateNetwork.canCheckNow(this)) return
        updateCheckRunning = true
        Thread {
            try {
                runBuiltinUpdateCheck(manual = false)
            } finally {
                runOnUiThread { updateCheckRunning = false }
            }
        }.start()
    }

    private fun runBuiltinUpdateCheck(manual: Boolean) {
        val assets = ProjectAssets(this)
        val manifest = assets.peekAvailableUpdate()
        if (manifest == null) {
            if (manual) {
                runOnUiThread { appendLog("当前已是最新脚本") }
            }
            return
        }
        val remoteVer = manifest.optInt("version_code", 0)
        if (UpdatePreferences.isAutoInstall(this)) {
            val ok = runCatching { assets.applyAvailableUpdate(manifest) }.getOrDefault(false)
            runOnUiThread {
                appendLog(if (ok) "已自动安装脚本更新 v$remoteVer" else "自动更新失败")
                if (ok) reloadLayoutUi()
                refreshStatus()
            }
            return
        }
        if (!manual && remoteVer <= UpdatePreferences.declinedVersion(this)) {
            return
        }
        if (!manual && !UpdateNetwork.canCheckNow(this)) {
            return
        }
        if (!manual && updateDialogShown) return
        if (!manual) UpdatePreferences.setPendingUpdateBadge(this, true)
        runOnUiThread { showUpdateDialog(manifest, remoteVer) }
    }

    private fun showUpdateDialog(manifest: JSONObject, remoteVer: Int) {
        if (updateDialogShown) return
        updateDialogShown = true
        val verName = manifest.optString("version_name", "")
        val changelog = manifest.optString("changelog", "").ifBlank { "（无更新说明）" }
        val title = if (verName.isNotBlank()) {
            "发现脚本更新 v$remoteVer ($verName)"
        } else {
            "发现脚本更新 v$remoteVer"
        }
        val message = buildString {
            append("更新说明：\n\n")
            append(changelog)
        }
        AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage(message)
            .setCancelable(true)
            .setPositiveButton("立即更新") { _, _ ->
                updateDialogShown = false
                Thread {
                    val ok = runCatching {
                        ProjectAssets(this).applyAvailableUpdate(manifest)
                    }.getOrDefault(false)
                    runOnUiThread {
                        appendLog(if (ok) "脚本已更新到 v$remoteVer" else "更新失败")
                        if (ok) {
                            UpdatePreferences.setPendingUpdateBadge(this, false)
                            reloadLayoutUi()
                        }
                        refreshStatus()
                    }
                }.start()
            }
            .setNeutralButton("跳过此版本") { _, _ ->
                updateDialogShown = false
                UpdatePreferences.setDeclinedVersion(this, remoteVer)
                appendLog("已跳过 v$remoteVer，有新版本前不再提示")
            }
            .setNegativeButton("稍后") { _, _ ->
                updateDialogShown = false
                appendLog("稍后再提醒更新")
            }
            .setOnDismissListener { updateDialogShown = false }
            .show()
    }

    private fun refreshStatus() {
        val cfg = ProjectAssets(this).loadConfig()
        val backend = DeviceAutomationBackend(cfg)
        val (overlayVer, _) = ProjectAssets(this).overlayVersionInfo()
        val verHint = if (overlayVer > cfg.versionCode) " · 热更 v$overlayVer" else ""
        val shizukuHint = when {
            cfg.inputMode.equals("shizuku", ignoreCase = true) && ShizukuInputBackend.isReady() ->
                " · Shizuku 就绪"
            cfg.inputMode.equals("shizuku", ignoreCase = true) && ShizukuInputBackend.isAvailable() ->
                " · Shizuku 待授权"
            else -> ""
        }
        statusText.text = when {
            backend.isReady() -> {
                val scheduleCfg = cfg.schedule
                val schedOn = SchedulePreferences.effectiveEnabled(this, scheduleCfg)
                val schedTime = SchedulePreferences.effectiveDailyTime(this, scheduleCfg)
                val schedHint = if (schedOn && schedTime.isNotBlank()) " · 每日 $schedTime" else ""
                if (backend.usingRoot()) "就绪 — root/Shizuku 模式$verHint$shizukuHint$schedHint"
                else "就绪 — 可运行脚本$verHint$shizukuHint$schedHint"
            }
            backend.usingRoot() && !RootShell.isAvailable() ->
                "root 模式：等待 su 授权（见设置）"
            backend.needsAccessibility() && !AutomationAccessibilityService.isConnected() ->
                "请开启无障碍服务（右上角设置）"
            backend.needsMediaProjection() && !CaptureSession.isActive() ->
                "请授权屏幕录制（右上角设置）"
            else -> getString(R.string.status_ready)
        }
    }

    private fun appendLog(msg: String) {
        logText.append("$msg\n")
        OverlayLog.notify(msg)
    }

    companion object {
        @Volatile
        var logSink: ((String) -> Unit)? = null

        private const val REQ_LOCATION = 4001
        private const val REQ_NOTIFICATIONS = 4002
    }
}
