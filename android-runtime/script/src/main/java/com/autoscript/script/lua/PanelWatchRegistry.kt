package com.autoscript.script.lua

import org.luaj.vm2.Globals
import org.luaj.vm2.LuaFunction
import org.luaj.vm2.LuaValue

/** 注册 panel.watch 回调，控件值变化时触发。 */
object PanelWatchRegistry {
    private val watches = linkedMapOf<String, MutableList<LuaFunction>>()

    fun clear() {
        watches.clear()
    }

    fun register(id: String, fn: LuaFunction) {
        val list = watches.getOrPut(id) { mutableListOf() }
        if (!list.contains(fn)) list.add(fn)
    }

    fun unregister(id: String, fn: LuaFunction?) {
        if (fn == null) {
            watches.remove(id)
            return
        }
        watches[id]?.remove(fn)
    }

    fun notify(globals: Globals, id: String, value: String) {
        val list = watches[id] ?: return
        val arg = LuaValue.valueOf(value)
        for (fn in list.toList()) {
            try {
                fn.invoke(arg)
            } catch (_: Exception) {
                // 忽略单次 watch 回调错误，避免拖垮面板
            }
        }
    }
}
