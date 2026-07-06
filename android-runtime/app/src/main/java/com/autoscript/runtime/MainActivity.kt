package com.autoscript.runtime

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.widget.Button
import android.widget.ImageButton
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.autoscript.core.accessibility.AutomationAccessibilityService
import com.autoscript.core.backend.DeviceAutomationBackend
import com.autoscript.core.capture.CaptureSession
import com.autoscript.core.capture.ScreenCaptureManager
import com.autoscript.core.log.ScriptLog
import com.autoscript.core.license.LicenseStore
import com.autoscript.core.license.LicenseVerifier
import com.autoscript.core.project.ProjectAssets
import com.autoscript.core.root.RootShell
import com.autoscript.core.root.ShizukuInputBackend
import com.autoscript.core.update.UpdateNetwork
import com.autoscript.core.update.UpdatePreferences
import com.autoscript.core.update.UpdateServer
import com.autoscript.runtime.shizuku.ShizukuShell
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    private lateinit var capture: ScreenCaptureManager
    private lateinit var statusText: TextView
    private lateinit var logText: TextView
    private var autoRun = false
    private var autoRunTriggered = false
    private var autoRunAttempts = 0
    private var captureRequested = false
    private var updateDialogShown = false
    private var updateCheckRunning = false
    private val handler = Handler(Looper.getMainLooper())

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

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if (logSink != null) logSink = null
        ShizukuShell.unbind()
        super.onDestroy()
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
        scheduleAutoRun()
        scheduleBuiltinUpdateCheck()
    }

    private fun requestOverlayAndStart() {
        if (Settings.canDrawOverlays(this)) {
            OverlayService.start(this)
            appendLog("浮动面板已启动（点标题栏可拖动）")
            return
        }
        AlertDialog.Builder(this)
            .setTitle("悬浮窗权限")
            .setMessage("按键精灵式浮动面板需要「显示在其他应用上层」权限。可在左上角设置中授权。")
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
            appendLog("auto_run: 等待就绪超时（请在左上角设置中完成授权）")
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
            .setMessage("本脚本需验证卡密后运行。也可在左上角设置中验证。")
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
                else -> appendLog("环境未就绪，请打开左上角设置")
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
                        if (ok) UpdatePreferences.setPendingUpdateBadge(this, false)
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
            backend.isReady() ->
                if (backend.usingRoot()) "就绪 — root/Shizuku 模式$verHint$shizukuHint"
                else "就绪 — 可运行脚本$verHint$shizukuHint"
            backend.usingRoot() && !RootShell.isAvailable() ->
                "root 模式：等待 su 授权（见设置）"
            backend.needsAccessibility() && !AutomationAccessibilityService.isConnected() ->
                "请开启无障碍服务（左上角设置）"
            backend.needsMediaProjection() && !CaptureSession.isActive() ->
                "请授权屏幕录制（左上角设置）"
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
    }
}
