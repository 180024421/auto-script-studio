package com.autoscript.script.saocheng

import android.content.Context
import com.autoscript.core.backend.AutomationBackend
import com.autoscript.core.script.ScriptCancelToken
import com.autoscript.vision.util.FrameUtils
import kotlinx.coroutines.delay

/** 扫城主循环：截屏 → YOLO+OCR 状态机 → 点击，与 GameBot / saocheng_pc_debug 行为一致。 */
class SaochengRunner(
    private val context: Context,
    private val backend: AutomationBackend,
    private val onLog: (String) -> Unit,
) {
    private var flowStep = "init"
    private var yolo: YoloDetector? = null
    private var ocr: OcrHelper? = null
    private var engine: SaochengFlowEngine? = null
    private val configStore = SaochengConfigStore(context)

    suspend fun run(conf: Float, auto: Boolean) {
        SaochengPanelSync.syncToStore(context)
        CityData.load(context)

        val det = yolo ?: YoloDetector(context).also { yolo = it }
        val ocrEngine = ocr ?: OcrHelper().also { ocr = it }
        val eng = engine ?: SaochengFlowEngine(det, ocrEngine, configStore).also { engine = it }
        eng.yoloConf = conf

        if (!det.ready) {
            onLog("YOLO 未就绪: ${det.loadError ?: "未知"}")
            return
        }

        val cfg = configStore.loadConfig()
        if (cfg.cities.isEmpty()) {
            onLog("请先在面板填写城池 ID（city_id）并勾选武将")
            return
        }
        if (cfg.heroes.none { it.enabled }) {
            onLog("请至少勾选一个武将")
            return
        }

        onLog("扫城启动 conf=$conf 城池=${cfg.cities} 武将=${cfg.heroes.filter { it.enabled }.map { it.name }}")
        flowStep = "init"
        eng.huanyeClicks = 0
        eng.fixedPointClicks = 0
        eng.activeHeroName = ""
        eng.activeHeroSlot = 0

        do {
            ScriptCancelToken.check()
            val frame = backend.capture()
            val bmp = FrameUtils.toBitmap(frame)
            try {
                val result = eng.analyze(bmp, flowStep, bmp.width, bmp.height)
                val respStep = result.step
                val nextStep = result.nextStep
                    ?: SaochengFlowEngine.SAOCHENG_NEXT_STEP[respStep]
                    ?: respStep
                flowStep = nextStep
                if (result.huanyeClicks > 0) eng.huanyeClicks = result.huanyeClicks

                onLog("← $respStep → 下轮 $nextStep | ${result.message}")
                if (YoloScreenMapper.lastDebugInfo.isNotBlank()) {
                    onLog("   YOLO: ${YoloScreenMapper.lastDebugInfo}")
                }
                result.clicks.forEachIndexed { i, click ->
                    ScriptCancelToken.check()
                    backend.tap(click.x, click.y)
                    onLog("   点击#${i + 1} (${click.x},${click.y})")
                    delay(clickDelayMs(respStep))
                }
                if (!auto) break
                delay(waitMs(nextStep))
            } finally {
                if (!bmp.isRecycled) bmp.recycle()
            }
        } while (auto)
    }

    private fun clickDelayMs(step: String): Long = when (step) {
        "map_opened", "click_city", "after_city_click" -> 1200L
        "guozhan_battle" -> 600L
        "scan_setup" -> 1000L
        else -> 800L
    }

    private fun waitMs(step: String): Long = when (step) {
        "navigate_map" -> 2000L
        "map_opened" -> 3500L
        "click_city" -> 2500L
        "after_city_click" -> 1500L
        "click_xuezhan" -> 2000L
        "click_dispatch" -> 2500L
        "minimize" -> 1500L
        "after_minimize" -> 2000L
        "wait_guozhan" -> 2000L
        "guozhan_battle" -> 1200L
        "wait_next_hour" -> 30_000L
        "stop_blood_war" -> 2000L
        else -> 1500L
    }
}
