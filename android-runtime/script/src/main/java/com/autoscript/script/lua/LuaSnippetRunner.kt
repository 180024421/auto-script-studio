package com.autoscript.script.lua

import com.autoscript.core.backend.AutomationBackend
import com.autoscript.core.project.ProjectAssets
import com.autoscript.vision.VisionEngine
import org.luaj.vm2.lib.jse.JsePlatform

/** 在浮动面板等场景执行短 Lua 片段。 */
object LuaSnippetRunner {

    suspend fun run(
        assets: ProjectAssets,
        backend: AutomationBackend,
        lua: String,
        onLog: (String) -> Unit,
    ) {
        if (lua.isBlank()) return
        val config = assets.loadConfig()
        val vision = VisionEngine(assets, assets.appContext(), config.ocrMode)
        try {
            val bridge = AutoScriptBridge(backend, vision, config, onLog, config.defaultYoloModel)
            val globals = JsePlatform.standardGlobals()
            LuaBindings.install(globals, bridge, onLog)
            globals.load(lua, "snippet").call()
        } finally {
            vision.release()
        }
    }
}
