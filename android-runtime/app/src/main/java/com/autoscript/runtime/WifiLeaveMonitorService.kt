package com.autoscript.runtime

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.widget.Toast
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.autoscript.core.project.WifiLeavePreferences

/**
 * 监听公司 WiFi：最早下班时刻之后从公司 SSID 断开则 Toast 并直接打开钉钉。
 */
class WifiLeaveMonitorService : Service() {

    private val handler = Handler(Looper.getMainLooper())
    private var connectivityManager: ConnectivityManager? = null
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    private var wasOnCompanyWifi = false

    private val pollRunnable = object : Runnable {
        override fun run() {
            evaluateWifiState(triggerOnLeave = true)
            handler.postDelayed(this, POLL_MS)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopSelfSafe()
                return START_NOT_STICKY
            }
            else -> {
                if (!WifiLeavePreferences.isEnabled(this)) {
                    stopSelfSafe()
                    return START_NOT_STICKY
                }
                startForeground(NOTIFICATION_ID, buildNotification("监听公司 WiFi 中"))
                ensureListening()
                evaluateWifiState(triggerOnLeave = false)
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        stopListening()
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    private fun ensureListening() {
        if (networkCallback != null) return
        val cm = getSystemService(ConnectivityManager::class.java) ?: return
        connectivityManager = cm
        val request = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .build()
        val cb = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                handler.post { evaluateWifiState(triggerOnLeave = true) }
            }

            override fun onLost(network: Network) {
                handler.post { evaluateWifiState(triggerOnLeave = true) }
            }

            override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) {
                handler.post { evaluateWifiState(triggerOnLeave = true) }
            }
        }
        networkCallback = cb
        runCatching { cm.registerNetworkCallback(request, cb) }
        handler.removeCallbacks(pollRunnable)
        handler.postDelayed(pollRunnable, POLL_MS)
    }

    private fun stopListening() {
        networkCallback?.let { cb ->
            connectivityManager?.unregisterNetworkCallback(cb)
        }
        networkCallback = null
        handler.removeCallbacks(pollRunnable)
    }

    private fun evaluateWifiState(triggerOnLeave: Boolean) {
        if (!WifiLeavePreferences.isEnabled(this)) {
            stopSelfSafe()
            return
        }
        val target = WifiLeavePreferences.ssid(this)
        val current = currentWifiSsid()
        val onCompany = !current.isNullOrBlank() &&
            current.equals(target, ignoreCase = true)

        if (onCompany) {
            wasOnCompanyWifi = true
            updateNotification("已连公司 WiFi：$target")
            return
        }

        // 当前不在公司 WiFi
        if (triggerOnLeave && wasOnCompanyWifi) {
            wasOnCompanyWifi = false
            maybeTriggerLeave()
        } else if (!wasOnCompanyWifi) {
            updateNotification("未连公司 WiFi，等待上班连接")
        }
    }

    private fun maybeTriggerLeave() {
        if (WifiLeavePreferences.alreadyTriggeredToday(this)) {
            updateNotification("今日已提醒过下班打卡")
            return
        }
        if (!WifiLeavePreferences.isAfterEarliest(this)) {
            updateNotification("已离开公司 WiFi（未到 ${WifiLeavePreferences.earliestTime(this)}，不提醒）")
            return
        }
        WifiLeavePreferences.markTriggeredToday(this)
        updateNotification("检测到离开公司 WiFi，正在打开钉钉…")
        handler.post {
            Toast.makeText(this, "下班了：正在打开钉钉打卡", Toast.LENGTH_LONG).show()
        }
        openDingTalk()
    }

    private fun openDingTalk() {
        val pkg = DINGTALK_PACKAGE
        val launch = packageManager.getLaunchIntentForPackage(pkg)
        if (launch == null) {
            handler.post {
                Toast.makeText(this, "未安装钉钉，无法自动打开", Toast.LENGTH_LONG).show()
            }
            updateNotification("未安装钉钉")
            return
        }
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { startActivity(launch) }
            .onFailure {
                handler.post {
                    Toast.makeText(this, "打开钉钉失败: ${it.message}", Toast.LENGTH_LONG).show()
                }
            }
    }

    private fun currentWifiSsid(): String? = WifiLeavePreferences.currentConnectedSsid(this)

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

    private fun updateNotification(text: String) {
        val mgr = getSystemService(NotificationManager::class.java) ?: return
        mgr.notify(NOTIFICATION_ID, buildNotification(text))
    }

    private fun buildNotification(text: String): Notification {
        val channelId = "wifi_leave_monitor"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = getSystemService(NotificationManager::class.java)
            mgr.createNotificationChannel(
                NotificationChannel(channelId, "下班 WiFi 监听", NotificationManager.IMPORTANCE_LOW),
            )
        }
        return NotificationCompat.Builder(this, channelId)
            .setContentTitle("下班打卡提醒")
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_launcher)
            .setOngoing(true)
            .build()
    }

    private fun stopSelfSafe() {
        stopListening()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    companion object {
        const val ACTION_START = "com.autoscript.runtime.WIFI_LEAVE_START"
        const val ACTION_STOP = "com.autoscript.runtime.WIFI_LEAVE_STOP"
        private const val NOTIFICATION_ID = 1003
        private const val POLL_MS = 20_000L
        private const val DINGTALK_PACKAGE = "com.alibaba.android.rimet"

        fun start(context: Context) {
            if (!WifiLeavePreferences.isEnabled(context)) return
            val intent = Intent(context, WifiLeaveMonitorService::class.java).apply {
                action = ACTION_START
            }
            ContextCompat.startForegroundService(context, intent)
        }

        fun stop(context: Context) {
            val intent = Intent(context, WifiLeaveMonitorService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }

        fun sync(context: Context) {
            if (WifiLeavePreferences.isEnabled(context)) start(context) else stop(context)
        }
    }
}
