package com.autoscript.runtime

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.CheckBox
import android.widget.ImageButton
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.autoscript.core.accessibility.AutomationAccessibilityService
import com.autoscript.core.backend.DeviceAutomationBackend
import com.autoscript.core.capture.CaptureSession
import com.autoscript.core.capture.ScreenCaptureManager
import com.autoscript.core.license.LicenseStore
import com.autoscript.core.license.LicenseVerifier
import com.autoscript.core.perf.PerfMonitor
import com.autoscript.core.project.ProjectAssets
import com.autoscript.core.root.RootShell
import com.autoscript.core.root.ShizukuInputBackend
import com.autoscript.core.update.UpdatePreferences
import com.autoscript.core.update.UpdateServer
import com.autoscript.runtime.shizuku.ShizukuShell
import org.json.JSONObject
import java.io.File

class SettingsActivity : AppCompatActivity() {

    private lateinit var capture: ScreenCaptureManager
    private lateinit var authStatusText: TextView
    private lateinit var updateServerText: TextView
    private lateinit var perfStatsText: TextView
    private var updateDialogShown = false

    private val importZipLauncher = registerForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.OpenDocument(),
    ) { uri ->
        if (uri == null) return@registerForActivityResult
        runCatching {
            val tmp = File(cacheDir, "local_update.zip")
            contentResolver.openInputStream(uri)?.use { input ->
                tmp.outputStream().use { output -> input.copyTo(output) }
            } ?: throw IllegalStateException("无法读取文件")
            val ok = ProjectAssets(this).importUpdateZip(tmp)
            tmp.delete()
            if (ok) {
                AlertDialog.Builder(this)
                    .setTitle("导入成功")
                    .setMessage("本地更新包已应用")
                    .setPositiveButton("确定", null)
                    .show()
            } else {
                showToastDialog("导入失败", "本地更新包格式无效或校验失败")
            }
        }.onFailure {
            showToastDialog("导入失败", it.message ?: "未知错误")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)
        capture = ScreenCaptureManager(this)

        authStatusText = findViewById(R.id.authStatusText)
        updateServerText = findViewById(R.id.updateServerText)
        perfStatsText = findViewById(R.id.perfStatsText)

        findViewById<ImageButton>(R.id.btnBack).setOnClickListener { finish() }
        findViewById<Button>(R.id.btnAccessibility).setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }
        findViewById<Button>(R.id.btnCapture).setOnClickListener {
            startActivityForResult(capture.createCaptureIntent(), ScreenCaptureManager.REQUEST_MEDIA_PROJECTION)
        }
        findViewById<Button>(R.id.btnOverlayPerm).setOnClickListener { requestOverlayPermission() }
        findViewById<Button>(R.id.btnLicense).setOnClickListener { promptLicense() }
        findViewById<Button>(R.id.btnShizuku).setOnClickListener {
            ShizukuShell.requestPermission()
        }
        findViewById<Button>(R.id.btnCheckUpdate).setOnClickListener { checkScriptUpdate() }
        findViewById<Button>(R.id.btnImportUpdate).setOnClickListener {
            importZipLauncher.launch(arrayOf("application/zip", "application/x-zip-compressed"))
        }

        findViewById<CheckBox>(R.id.chkEnableUpdate)?.apply {
            isChecked = UpdatePreferences.isCheckEnabled(this@SettingsActivity)
            setOnCheckedChangeListener { _, checked ->
                UpdatePreferences.setCheckEnabled(this@SettingsActivity, checked)
                findViewById<CheckBox>(R.id.chkAutoUpdate)?.isEnabled = checked
                if (!checked) {
                    UpdatePreferences.setAutoInstall(this@SettingsActivity, false)
                    findViewById<CheckBox>(R.id.chkAutoUpdate)?.isChecked = false
                }
            }
        }
        findViewById<CheckBox>(R.id.chkAutoUpdate)?.apply {
            isChecked = UpdatePreferences.isAutoInstall(this@SettingsActivity)
            isEnabled = UpdatePreferences.isCheckEnabled(this@SettingsActivity)
            setOnCheckedChangeListener { _, checked ->
                UpdatePreferences.setAutoInstall(this@SettingsActivity, checked)
            }
        }
        findViewById<CheckBox>(R.id.chkWifiOnly)?.apply {
            isChecked = UpdatePreferences.isWifiOnly(this@SettingsActivity)
            setOnCheckedChangeListener { _, checked ->
                UpdatePreferences.setWifiOnly(this@SettingsActivity, checked)
            }
        }
        findViewById<CheckBox>(R.id.chkSilentNight)?.apply {
            val (start, end) = UpdatePreferences.silentHours(this@SettingsActivity)
            isChecked = start == 23 && end == 7
            setOnCheckedChangeListener { _, checked ->
                if (checked) UpdatePreferences.setSilentHours(this@SettingsActivity, 23, 7)
                else UpdatePreferences.setSilentHours(this@SettingsActivity, -1, -1)
            }
        }

        refreshUpdateServerHint()
        ShizukuShell.init()
    }

    override fun onResume() {
        super.onResume()
        refreshAuthStatus()
        refreshPerfStats()
    }

    private fun refreshPerfStats() {
        val backend = DeviceAutomationBackend(ProjectAssets(this).loadConfig())
        perfStatsText.text = buildString {
            appendLine("点击: ${backend.inputModeLabel()} · 截屏: ${backend.captureModeLabel()}")
            append(PerfMonitor.summary())
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == ScreenCaptureManager.REQUEST_MEDIA_PROJECTION) {
            if (ScreenCaptureManager.handleActivityResult(capture, resultCode, data)) {
                CaptureSession.bind(capture)
            }
            refreshAuthStatus()
        }
    }

    private fun refreshAuthStatus() {
        val cfg = ProjectAssets(this).loadConfig()
        val backend = DeviceAutomationBackend(cfg)
        val verifier = LicenseVerifier(this, cfg.license, cfg.packageId)

        val lines = buildList {
            add(
                line(
                    "无障碍服务",
                    !backend.needsAccessibility() || AutomationAccessibilityService.isConnected(),
                ),
            )
            add(
                line(
                    "屏幕录制",
                    !backend.needsMediaProjection() || CaptureSession.isActive(),
                ),
            )
            add(line("悬浮窗", Settings.canDrawOverlays(this)))
            if (cfg.license.enabled) {
                add(line("卡密验证", verifier.isLicensed()))
            }
            if (cfg.inputMode.equals("shizuku", ignoreCase = true)) {
                add(
                    line(
                        "Shizuku 触控",
                        ShizukuInputBackend.isReady() || ShizukuInputBackend.isAvailable(),
                    ),
                )
            }
            if (backend.usingRoot()) {
                add(line("Root", RootShell.isAvailable()))
            }
            val (overlayVer, overlayName) = ProjectAssets(this).overlayVersionInfo()
            val verText = if (overlayName.isNotBlank()) "v$overlayVer ($overlayName)" else "v$overlayVer"
            add("脚本版本：$verText")
        }
        authStatusText.text = lines.joinToString("\n")
    }

    private fun line(label: String, ok: Boolean): String =
        "$label：${if (ok) "已授权" else "未授权"}"

    private fun refreshUpdateServerHint() {
        updateServerText.text = if (UpdateServer.isConfigured()) {
            "更新服务器：${UpdateServer.apiBase()}"
        } else {
            "更新服务器：未配置（打包时需设置 license.api_base）"
        }
    }

    private fun requestOverlayPermission() {
        if (Settings.canDrawOverlays(this)) {
            showToastDialog("悬浮窗", "悬浮窗权限已授予")
            refreshAuthStatus()
            return
        }
        AlertDialog.Builder(this)
            .setTitle("悬浮窗权限")
            .setMessage("浮动面板需要「显示在其他应用上层」权限，请在设置中允许后返回。")
            .setPositiveButton("去设置") { _, _ ->
                startActivity(
                    Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:$packageName"),
                    ),
                )
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun promptLicense() {
        val input = android.widget.EditText(this)
        input.hint = "请输入卡密"
        LicenseStore.getCode(this)?.let { input.setText(it) }
        AlertDialog.Builder(this)
            .setTitle("卡密验证")
            .setMessage("本脚本需验证卡密后运行（jiaoben）")
            .setView(input)
            .setPositiveButton("验证") { _, _ ->
                val code = input.text?.toString()?.trim().orEmpty()
                val cfg = ProjectAssets(this).loadConfig()
                val verifier = LicenseVerifier(this, cfg.license, cfg.packageId)
                if (verifier.verifyAndBind(code)) {
                    showToastDialog("验证成功", "卡密已绑定")
                    refreshAuthStatus()
                } else {
                    showToastDialog("验证失败", "卡密无效或网络错误")
                }
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun checkScriptUpdate() {
        if (!UpdateServer.isConfigured()) {
            showToastDialog("无法检测", "未配置更新服务器")
            return
        }
        if (!UpdatePreferences.isCheckEnabled(this)) {
            showToastDialog("无法检测", "更新检测已关闭，请先勾选「启用更新检测」")
            return
        }
        Thread {
            val assets = ProjectAssets(this)
            val manifest = assets.peekAvailableUpdate()
            runOnUiThread {
                if (manifest == null) {
                    showToastDialog("检查完成", "当前已是最新脚本")
                    return@runOnUiThread
                }
                val remoteVer = manifest.optInt("version_code", 0)
                if (UpdatePreferences.isAutoInstall(this)) {
                    Thread {
                        val ok = runCatching { assets.applyAvailableUpdate(manifest) }.getOrDefault(false)
                        runOnUiThread {
                            showToastDialog(
                                if (ok) "更新成功" else "更新失败",
                                if (ok) "脚本已更新到 v$remoteVer" else "请稍后重试",
                            )
                            refreshAuthStatus()
                        }
                    }.start()
                    return@runOnUiThread
                }
                showUpdateDialog(manifest, remoteVer)
            }
        }.start()
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
        AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage("更新说明：\n\n$changelog")
            .setCancelable(true)
            .setPositiveButton("立即更新") { _, _ ->
                updateDialogShown = false
                Thread {
                    val ok = runCatching {
                        ProjectAssets(this).applyAvailableUpdate(manifest)
                    }.getOrDefault(false)
                    runOnUiThread {
                        showToastDialog(
                            if (ok) "更新成功" else "更新失败",
                            if (ok) "脚本已更新到 v$remoteVer" else "请稍后重试",
                        )
                        refreshAuthStatus()
                    }
                }.start()
            }
            .setNeutralButton("跳过此版本") { _, _ ->
                updateDialogShown = false
                UpdatePreferences.setDeclinedVersion(this, remoteVer)
            }
            .setNegativeButton("稍后", null)
            .setOnDismissListener { updateDialogShown = false }
            .show()
    }

    private fun showToastDialog(title: String, message: String) {
        AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage(message)
            .setPositiveButton("确定", null)
            .show()
    }
}
