package com.autoscript.script.lua

import com.autoscript.core.backend.AutomationBackend
import com.autoscript.core.project.ProjectAssets
import com.autoscript.core.project.ProjectConfig
import com.autoscript.core.script.ScriptTrace
import com.autoscript.script.ScriptRuntime
import com.autoscript.vision.VisionEngine
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import org.luaj.vm2.Globals
import org.luaj.vm2.LuaError
import org.luaj.vm2.LuaValue
import org.luaj.vm2.lib.OneArgFunction
import org.luaj.vm2.lib.TwoArgFunction
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
        vision = VisionEngine(
            assets,
            assets.appContext(),
            config.ocrMode,
            yoloImgsz = config.perf.yoloImgsz,
            perf = config.perf,
        )
        bridge = AutoScriptBridge(backend, vision, config, onLog, config.defaultYoloModel)
        val source = assets.readEntryScript()
        onLog("开始 Lua: ${config.entry}")
        try {
            withContext(Dispatchers.Default) {
                coroutineScope {
                    LuaBridgeRunner.bind(this)
                    ScriptTrace.configure(
                        enabled = true,
                        tagFilter = null,
                        log = onLog,
                    )
                    try {
                        LuaBridgeRunner.await { bridge.warmupYolo() }
                        val globals: Globals = JsePlatform.standardGlobals()
                        installLibLoader(globals)
                        LuaBindings.install(globals, bridge, onLog)
                        LuaBindings.installCoroutineYield(globals, bridge)
                        val chunk = globals.load(source, config.entry)
                        chunk.call()
                    } finally {
                        LuaBridgeRunner.unbind()
                        ScriptTrace.reset()
                    }
                }
            }
            onLog("Lua 脚本完成")
        } catch (e: LuaError) {
            throw IllegalStateException("Lua 错误: ${e.message}", e)
        }
    }

    private fun installLibLoader(globals: Globals) {
        val loader = object : TwoArgFunction() {
            override fun call(modname: LuaValue, path: LuaValue): LuaValue {
                val name = modname.checkjstring()
                val rel = when {
                    name.startsWith("lib/") -> "$name.lua"
                    name.endsWith(".lua") -> "lib/$name"
                    else -> "lib/$name.lua"
                }
                if (!assets.exists(rel)) {
                    return LuaValue.NIL
                }
                val src = assets.readYaml(rel)
                val chunk = globals.load(src, rel)
                val result = chunk.call()
                return if (result.isnil()) LuaValue.TRUE else result
            }
        }
        globals.get("package").checktable().get("searchers").checktable().set(2, loader)
        globals.set("require", object : OneArgFunction() {
            private val loaded = globals.get("package").checktable().get("loaded").checktable()
            override fun call(modname: LuaValue): LuaValue {
                val name = modname.checkjstring()
                val cached = loaded.get(name)
                if (!cached.isnil()) return cached
                val result = loader.call(modname, LuaValue.NIL)
                if (result.isnil()) throw LuaError("module '$name' not found")
                loaded.set(name, result)
                return result
            }
        })
    }

    override fun release() {
        if (::vision.isInitialized) vision.release()
    }
}
