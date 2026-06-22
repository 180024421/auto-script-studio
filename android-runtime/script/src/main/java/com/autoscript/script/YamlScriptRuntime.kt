package com.autoscript.script

import com.autoscript.core.backend.AutomationBackend
import com.autoscript.core.project.ProjectAssets

class YamlScriptRuntime(
    private val assets: ProjectAssets,
    private val backend: AutomationBackend,
    private val onLog: (String) -> Unit,
) : ScriptRuntime {

    private val engine = ScriptEngine(assets, backend, onLog)

    override suspend fun run() {
        engine.run("main")
    }

    override fun release() {
        engine.release()
    }
}
