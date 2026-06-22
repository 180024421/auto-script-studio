package com.autoscript.runtime

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.autoscript.core.accessibility.AutomationAccessibilityService
import com.autoscript.core.capture.CaptureSession
import com.autoscript.core.capture.ScreenCaptureManager
import com.autoscript.core.project.ProjectAssets

class MainActivity : AppCompatActivity() {

    private lateinit var capture: ScreenCaptureManager
    private lateinit var statusText: TextView
    private lateinit var logText: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        capture = ScreenCaptureManager(this)
        CaptureSession.bind(capture)

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

        appendLog("工程: ${runCatching { ProjectAssets(this).loadConfig().name }.getOrElse { "未打包" }}")
        logSink = { msg -> runOnUiThread { appendLog(msg) } }
    }

    override fun onDestroy() {
        if (logSink != null) logSink = null
        super.onDestroy()
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == ScreenCaptureManager.REQUEST_MEDIA_PROJECTION) {
            if (ScreenCaptureManager.handleActivityResult(capture, resultCode, data)) {
                appendLog("屏幕录制已授权")
            } else {
                appendLog("屏幕录制授权被拒绝")
            }
            refreshStatus()
        }
    }

    private fun startScript() {
        if (!AutomationAccessibilityService.isConnected()) {
            appendLog("请先开启无障碍服务")
            return
        }
        if (!CaptureSession.isActive()) {
            appendLog("请先授权屏幕录制")
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
        val a11y = AutomationAccessibilityService.isConnected()
        val cap = CaptureSession.isActive()
        statusText.text = when {
            a11y && cap -> "就绪 — 可运行脚本"
            !a11y && !cap -> getString(R.string.status_ready)
            !a11y -> "请开启无障碍服务"
            else -> "请授权屏幕录制"
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
