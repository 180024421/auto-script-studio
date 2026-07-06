package com.autoscript.core.root

import com.autoscript.core.log.ScriptLog

/**
 * Shizuku 触控：通过 app 模块 [ShizukuShell] 注入 shell 执行器。
 * input_mode=shizuku 时由 [com.autoscript.core.backend.DeviceAutomationBackend] 选用。
 */
object ShizukuInputBackend {

    /** app 模块绑定 UserService 后注入，执行 shell 命令（如 input tap）。 */
    @Volatile
    var shellExec: ((String) -> Boolean)? = null

    fun isAvailable(): Boolean {
        return try {
            val cls = Class.forName("rikka.shizuku.Shizuku")
            val ping = cls.getMethod("pingBinder").invoke(null) as Boolean
            if (!ping) return false
            val perm = cls.getMethod("checkSelfPermission").invoke(null) as Int
            perm == 0 // PackageManager.PERMISSION_GRANTED
        } catch (_: Exception) {
            false
        }
    }

    fun isReady(): Boolean = isAvailable() && shellExec != null

    private fun exec(cmd: String): Boolean {
        val fn = shellExec
        if (fn == null) {
            ScriptLog.i("Shizuku 未绑定 UserService，请先授权 Shizuku")
            return false
        }
        return fn(cmd)
    }

    fun tap(x: Int, y: Int): Boolean = exec("input tap $x $y")

    fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int): Boolean =
        exec("input swipe $x1 $y1 $x2 $y2 $durationMs")

    fun longPress(x: Int, y: Int, durationMs: Int): Boolean {
        val d = durationMs.coerceAtLeast(100)
        return exec("input swipe $x $y $x $y $d")
    }
}
