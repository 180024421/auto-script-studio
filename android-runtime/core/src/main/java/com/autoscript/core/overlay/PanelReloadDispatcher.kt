package com.autoscript.core.overlay

/** 由运行时 APK 注册，供 Lua `bot.reloadPanel()` 刷新浮动面板（如应用列表）。 */
object PanelReloadDispatcher {

    @Volatile
    var reload: (() -> Unit)? = null

    fun requestReload(): Boolean {
        val fn = reload ?: return false
        fn.invoke()
        return true
    }
}
