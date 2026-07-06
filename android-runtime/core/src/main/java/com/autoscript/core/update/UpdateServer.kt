package com.autoscript.core.update

/**
 * 打包时写入的服务器地址（jiaoben / run-jane-script），运行时不可通过 project.json 关闭热更新。
 */
object UpdateServer {
    @Volatile
    private var apiBase: String = ""

    @Volatile
    private var appPackage: String = ""

    fun init(apiBase: String, appPackage: String) {
        this.apiBase = apiBase.trim().trimEnd('/')
        this.appPackage = appPackage.trim()
    }

    fun isConfigured(): Boolean = apiBase.isNotBlank() && appPackage.isNotBlank()

    fun manifestUrl(): String {
        if (!isConfigured()) return ""
        val base = apiBase
        val prefix = if (base.endsWith("/api", ignoreCase = true)) {
            base
        } else {
            "$base/api"
        }
        return "$prefix/script/update/manifest?app=$appPackage"
    }

    fun apiBase(): String = apiBase

    fun appPackage(): String = appPackage
}
