package com.autoscript.runtime

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.autoscript.core.accessibility.AutomationAccessibilityService
import com.autoscript.core.backend.DeviceAutomationBackend
import com.autoscript.core.capture.CaptureSession
import com.autoscript.core.capture.ScreenCaptureManager
import com.autoscript.core.log.ScriptLog
import com.autoscript.core.project.ProjectAssets
import com.autoscript.core.root.RootShell

class MainActivity : AppCompatActivity() {

    private lateinit var capture: ScreenCaptureManager
    private lateinit var statusText: TextView
    private lateinit var logText: TextView
    private var autoRun = false
    private var autoRunTriggered = false
    private var autoRunAttempts = 0
    private var captureRequested = false
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
        }

        statusText = findViewById(R.id.statusText)
        logText = findViewById(R.id.logText)

        findViewById<Button>(R.id.btnAccessibility).setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }
        findViewById<Button>(R.id.btnCapture).setOnClickListener {
            startActivityForResult(capture.createCaptureIntent(), ScreenCaptureManager.REQUEST_MEDIA_PROJECTION)
        }
        findViewById<Button>(R.id.btnStart).setOnClickListener { startScript() }
        findViewById<Button>(R.id.btnStop).setOnClickListener { stopScript() }
        findViewById<Button>(R.id.btnOverlay).setOnClickListener { requestOverlayAndStart() }

        appendLog("工程: ${runCatching { ProjectAssets(this).loadConfig().name }.getOrElse { "未打包" }}")
        logSink = { msg -> runOnUiThread { appendLog(msg) } }
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if (logSink != null) logSink = null
        super.onDestroy()
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
        scheduleAutoRun()
        if (Settings.canDrawOverlays(this)) {
            OverlayService.start(this)
        }
    }

    private fun requestOverlayAndStart() {
        if (Settings.canDrawOverlays(this)) {
            OverlayService.start(this)
            appendLog("浮动面板已启动")
            return
        }
        AlertDialog.Builder(this)
            .setTitle("悬浮窗权限")
            .setMessage("按键精灵式浮动面板需要「显示在其他应用上层」权限，请在设置中允许后返回。")
            .setPositiveButton("去设置") { _, _ ->
                val intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName"),
                )
                startActivity(intent)
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
                    .setMessage("找图/识字/YOLO 需要屏幕录制权限。无障碍截图模式（screenshot_mode: accessibility）可免录屏。")
                    .setPositiveButton("重试") { _, _ ->
                        startActivityForResult(
                            capture.createCaptureIntent(),
                            ScreenCaptureManager.REQUEST_MEDIA_PROJECTION,
                        )
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
            appendLog("auto_run: 等待就绪超时（无障碍/录屏/root）")
        }
    }

    private fun startScript() {
        val backend = automationBackend()
        if (!backend.isReady()) {
            when {
                backend.usingRoot() && !RootShell.isAvailable() ->
                    appendLog("root 模式：请在弹窗中允许 su 权限")
                backend.needsAccessibility() && !AutomationAccessibilityService.isConnected() ->
                    appendLog("请先开启无障碍服务")
                backend.needsMediaProjection() && !CaptureSession.isActive() ->
                    appendLog("请先授权屏幕录制")
                else -> appendLog("环境未就绪")
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

    private fun refreshStatus() {
        val backend = automationBackend()
        statusText.text = when {
            backend.isReady() ->
                if (backend.usingRoot()) "就绪 — root 模式（免无障碍/录屏）" else "就绪 — 可运行脚本"
            backend.usingRoot() && !RootShell.isAvailable() ->
                "root 模式：等待 su 授权"
            backend.needsAccessibility() && !AutomationAccessibilityService.isConnected() ->
                "请开启无障碍服务（或改用 input_mode: auto/root）"
            backend.needsMediaProjection() && !CaptureSession.isActive() ->
                "请授权屏幕录制"
            else -> getString(R.string.status_ready)
        }
    }

    private fun appendLog(msg: String) {
        logText.append("$msg\n")
    }

    companion object {
        @Volatile
        var logSink: ((String) -> Unit)? = null
    }
}
