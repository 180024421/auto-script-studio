package com.autoscript.core.capture

/**
 * 全局截屏会话，MainActivity 授权后供 ScriptRunnerService 复用。
 */
object CaptureSession {
    @Volatile
    private var manager: ScreenCaptureManager? = null

    fun bind(manager: ScreenCaptureManager) {
        this.manager = manager
    }

    fun get(): ScreenCaptureManager =
        manager ?: throw IllegalStateException("截屏未初始化，请先在主界面授权屏幕录制")

    fun isActive(): Boolean = manager?.isActive() == true
}
