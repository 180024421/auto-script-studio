package com.autoscript.runtime.shizuku

import android.content.ComponentName
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.IBinder
import com.autoscript.core.log.ScriptLog
import com.autoscript.core.root.ShizukuInputBackend
import com.autoscript.runtime.BuildConfig
import rikka.shizuku.Shizuku
import rikka.shizuku.Shizuku.UserServiceArgs

/**
 * 绑定 Shizuku UserService，向 core 模块注入 shell 执行器。
 */
object ShizukuShell {

    @Volatile
    private var userService: IUserService? = null

    @Volatile
    private var binding = false

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
            userService = IUserService.Stub.asInterface(binder)
            binding = false
            ShizukuInputBackend.shellExec = { cmd -> exec(cmd) }
            ScriptLog.i("Shizuku UserService 已连接")
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            userService = null
            ShizukuInputBackend.shellExec = null
            binding = false
            ScriptLog.i("Shizuku UserService 已断开")
        }
    }

    fun init() {
        if (!Shizuku.pingBinder()) return
        Shizuku.addRequestPermissionResultListener { _, grantResult ->
            if (grantResult == PackageManager.PERMISSION_GRANTED) {
                bind()
            }
        }
        Shizuku.addBinderReceivedListener { bind() }
        Shizuku.addBinderDeadListener {
            userService = null
            ShizukuInputBackend.shellExec = null
        }
        if (Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED) {
            bind()
        }
    }

    fun requestPermission() {
        if (!Shizuku.pingBinder()) {
            ScriptLog.i("未安装或未启动 Shizuku")
            return
        }
        if (Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED) {
            bind()
            return
        }
        Shizuku.requestPermission(0)
    }

    fun isReady(): Boolean = userService != null

    fun exec(cmd: String): Boolean {
        val svc = userService ?: return false
        return try {
            svc.execCommand(cmd) == 0
        } catch (e: Exception) {
            ScriptLog.i("Shizuku exec 异常: ${e.message}")
            false
        }
    }

    private fun bind() {
        if (userService != null || binding) return
        if (!Shizuku.pingBinder()) return
        if (Shizuku.checkSelfPermission() != PackageManager.PERMISSION_GRANTED) return
        binding = true
        val args = UserServiceArgs(
            ComponentName(BuildConfig.APPLICATION_ID, ShizukuUserService::class.java.name),
        ).daemon(false).processNameSuffix("shizuku_shell").debuggable(BuildConfig.DEBUG).version(1)
        try {
            Shizuku.bindUserService(args, connection)
        } catch (e: Exception) {
            binding = false
            ScriptLog.i("Shizuku bind 失败: ${e.message}")
        }
    }

    fun unbind() {
        if (userService == null && !binding) return
        try {
            val args = UserServiceArgs(
                ComponentName(BuildConfig.APPLICATION_ID, ShizukuUserService::class.java.name),
            )
            Shizuku.unbindUserService(args, connection, true)
        } catch (_: Exception) {
        }
        userService = null
        ShizukuInputBackend.shellExec = null
        binding = false
    }
}
