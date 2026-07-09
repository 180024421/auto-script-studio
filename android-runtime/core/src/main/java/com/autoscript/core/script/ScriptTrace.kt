package com.autoscript.core.script

/**
 * 脚本 trace 日志：bot.trace(tag, msg) 写入运行日志，可按 tag 过滤。
 */
object ScriptTrace {
    @Volatile private var enabled: Boolean = false
    @Volatile private var tagFilter: String? = null
    private var onLog: ((String) -> Unit)? = null

    fun configure(enabled: Boolean, tagFilter: String?, log: (String) -> Unit) {
        this.enabled = enabled
        this.tagFilter = tagFilter?.trim()?.takeIf { it.isNotEmpty() }
        onLog = log
    }

    fun reset() {
        enabled = false
        tagFilter = null
        onLog = null
    }

    fun trace(tag: String, msg: String) {
        if (!enabled) return
        val t = tag.trim()
        val filter = tagFilter
        if (filter != null && t != filter) return
        onLog?.invoke("[trace:$t] $msg")
    }
}
