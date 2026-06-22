package com.autoscript.script

import android.util.Log
import com.autoscript.core.backend.AutomationBackend
import com.autoscript.core.model.Rect
import com.autoscript.core.project.ProjectAssets
import com.autoscript.core.project.ProjectConfig
import com.autoscript.script.config.YamlConfigLoader
import com.autoscript.script.runner.ActionRunner
import com.autoscript.vision.VisionEngine
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.isActive
import kotlin.coroutines.coroutineContext

class ScriptEngine(
    private val assets: ProjectAssets,
    private val backend: AutomationBackend,
    private val onLog: (String) -> Unit = {},
) {
    private val loader = YamlConfigLoader()
    private lateinit var config: ProjectConfig
    private lateinit var workflow: Map<String, Any?>
    private lateinit var vision: VisionEngine
    private lateinit var runner: ActionRunner

    suspend fun run(flowName: String = "main") {
        config = assets.loadConfig()
        vision = VisionEngine(assets, config.ocrMode)
        runner = ActionRunner(backend, vision, config, onLog)

        var root = loader.load(assets.readEntryYaml())
        loader.mergeIncludes(root) { path -> assets.readYaml(path) }
        workflow = root

        @Suppress("UNCHECKED_CAST")
        val flows = workflow["flows"] as? Map<String, List<Any?>>
            ?: throw IllegalStateException("main.yaml 缺少 flows")
        val steps = flows[flowName]
            ?: throw IllegalStateException("未找到 flow: $flowName")
        @Suppress("UNCHECKED_CAST")
        val actions = workflow["actions"] as? Map<String, Map<String, Any?>> ?: emptyMap()

        onLog("开始 flow=$flowName, steps=${steps.size}")
        for ((i, step) in steps.withIndex()) {
            if (!coroutineContext.isActive) throw CancellationException()
            when (step) {
                is String -> {
                    val action = actions[step] ?: throw IllegalStateException("未知 action: $step")
                    runner.runAction(action, workflow)
                }
                is Map<*, *> -> {
                    @Suppress("UNCHECKED_CAST")
                    runner.runStep(step as Map<String, Any?>, workflow)
                }
                else -> throw IllegalStateException("非法步骤: $step")
            }
            onLog("步骤 ${i + 1} 完成")
        }
        onLog("flow=$flowName 完成")
    }

    fun release() {
        if (::vision.isInitialized) vision.release()
    }

    companion object {
        private const val TAG = "ScriptEngine"
    }
}

fun parseRoi(value: Any?): Rect? {
    if (value == null) return null
    if (value is List<*> && value.size == 4) {
        return Rect(
            (value[0] as Number).toInt(),
            (value[1] as Number).toInt(),
            (value[2] as Number).toInt(),
            (value[3] as Number).toInt(),
        )
    }
    if (value is Map<*, *>) {
        return Rect(
            (value["x"] as Number).toInt(),
            (value["y"] as Number).toInt(),
            (value["w"] as Number).toInt(),
            (value["h"] as Number).toInt(),
        )
    }
    return null
}

fun parseBgr(value: Any?): Triple<Int, Int, Int> {
    if (value is List<*> && value.size == 3) {
        return Triple(
            (value[0] as Number).toInt(),
            (value[1] as Number).toInt(),
            (value[2] as Number).toInt(),
        )
    }
    throw IllegalArgumentException("非法 bgr: $value")
}
