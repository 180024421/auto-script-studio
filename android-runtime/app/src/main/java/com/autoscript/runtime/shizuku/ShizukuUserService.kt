package com.autoscript.runtime.shizuku

import android.os.IBinder
import androidx.annotation.Keep
import java.io.BufferedReader
import java.io.InputStreamReader

/**
 * Shizuku UserService：在 shell 权限下执行 input 命令。
 */
@Keep
class ShizukuUserService : IUserService.Stub() {

    override fun destroy() {
        System.exit(0)
    }

    override fun execCommand(cmd: String): Int {
        val process = Runtime.getRuntime().exec(arrayOf("sh", "-c", cmd))
        val code = process.waitFor()
        if (code != 0) {
            BufferedReader(InputStreamReader(process.errorStream)).use { reader ->
                val err = reader.readText().trim()
                if (err.isNotBlank()) {
                    android.util.Log.w(TAG, "shizuku exec failed ($code): $err")
                }
            }
        }
        return code
    }

    companion object {
        private const val TAG = "ShizukuUserService"

        @Keep
        @JvmStatic
        fun main(args: Array<String>) {
            // Shizuku bindUserService entry
        }

        @Keep
        @JvmStatic
        private fun create(): IBinder = ShizukuUserService()
    }
}
