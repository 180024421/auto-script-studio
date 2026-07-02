package com.autoscript.core.script

import java.util.concurrent.atomic.AtomicBoolean

/** 脚本取消令牌，find* 轮询循环中检查。 */
object ScriptCancelToken {
    private val cancelled = AtomicBoolean(false)

    fun reset() {
        cancelled.set(false)
    }

    fun cancel() {
        cancelled.set(true)
    }

    fun isCancelled(): Boolean = cancelled.get()

    fun check() {
        if (cancelled.get()) throw kotlinx.coroutines.CancellationException("脚本已停止")
    }
}
