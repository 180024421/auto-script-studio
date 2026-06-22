package com.autoscript.script.lua

import com.autoscript.core.backend.AutomationBackend
import com.autoscript.core.project.ProjectAssets
import com.autoscript.core.project.ProjectConfig
import com.autoscript.script.ScriptRuntime
import com.autoscript.vision.VisionEngine
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.luaj.vm2.Globals
import org.luaj.vm2.LuaError
import org.luaj.vm2.lib.jse.JsePlatform

class LuaScriptEngine(
    private val assets: ProjectAssets,
    private val backend: AutomationBackend,
    private val onLog: (String) -> Unit = {},
) : ScriptRuntime {

    private lateinit var config: ProjectConfig
    private lateinit var vision: VisionEngine
    private lateinit var bridge: AutoScriptBridge

    override suspend fun run() {
        config = assets.loadConfig()
        if (!config.usesLua()) {
            throw IllegalStateException("工程 entry 不是 Lua: ${config.entry}")
        }
        vision = VisionEngine(assets, assets.appContext(), config.ocrMode)
        bridge = AutoScriptBridge(backend, vision, config, onLog, config.defaultYoloModel)
        val source = assets.readEntryScript()
        onLog("开始 Lua: ${config.entry}")
        try {
            withContext(Dispatchers.Default) {
                val globals: Globals = JsePlatform.standardGlobals()
                LuaBindings.install(globals, bridge, onLog)
                val chunk = globals.load(source, config.entry)
                chunk.call()
            }
            onLog("Lua 脚本完成")
        } catch (e: LuaError) {
            throw IllegalStateException("Lua 错误: ${e.message}", e)
        }
    }

    override fun release() {
        if (::vision.isInitialized) vision.release()
    }
}
