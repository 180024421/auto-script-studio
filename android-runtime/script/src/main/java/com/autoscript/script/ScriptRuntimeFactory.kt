package com.autoscript.script

import com.autoscript.core.backend.AutomationBackend
import com.autoscript.core.project.ProjectAssets
import com.autoscript.core.project.ProjectConfig
import com.autoscript.script.lua.LuaScriptEngine

object ScriptRuntimeFactory {

    fun create(
        assets: ProjectAssets,
        backend: AutomationBackend,
        onLog: (String) -> Unit,
    ): ScriptRuntime {
        val config = assets.loadConfig()
        return if (config.usesLua()) {
            LuaScriptEngine(assets, backend, onLog)
        } else {
            YamlScriptRuntime(assets, backend, onLog)
        }
    }
}
