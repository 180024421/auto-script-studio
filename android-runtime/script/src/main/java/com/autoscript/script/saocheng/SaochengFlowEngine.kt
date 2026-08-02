package com.autoscript.script.saocheng

import android.graphics.Bitmap

data class FlowClick(val x: Int, val y: Int)

data class FlowResult(
    val step: String,
    val message: String = "",
    val clicks: List<FlowClick> = emptyList(),
    val skip: Boolean = false,
    val nextStep: String? = null,
    val huanyeClicks: Int = 0,
    val fixedPointClicks: Int = 0,
    val activeHeroName: String = "",
    val activeHeroSlot: Int = 0,
    val detections: List<YoloDetection> = emptyList(),
)

class SaochengFlowEngine(
    private val yolo: YoloDetector,
    private val ocr: OcrHelper,
    private val store: SaochengConfigStore,
) {
    var huanyeClicks: Int = 0
    var fixedPointClicks: Int = 0
    var activeHeroName: String = ""
    var activeHeroSlot: Int = 0
    var yoloConf: Float = FlowConstants.YOLO_CONF

    suspend fun analyze(
        bitmap: Bitmap,
        step: String,
        fullW: Int,
        fullH: Int,
        cxOff: Int = 0,
        cyOff: Int = 0,
    ): FlowResult {
        val cfg = store.loadConfig()
        val st = store.loadState()
        val fw = if (fullW > 0) fullW else bitmap.width
        val fh = if (fullH > 0) fullH else bitmap.height
        var currentStep = step.ifBlank { "init" }

        if (currentStep == "wait_next_hour") {
            if (store.isNextHourReached(st)) {
                store.clearWaitNextHour(st)
                return resp("init", "已到新整点，重新开始扫城")
            }
            return resp("wait_next_hour", "推城次数已满，等待下一个整点")
        }

        if (st.waitingNextHour && currentStep != "wait_next_hour") {
            if (store.isNextHourReached(st)) {
                store.clearWaitNextHour(st)
            } else {
                return resp("wait_next_hour", "推城次数已满，等待下一个整点")
            }
        }

        if (store.allEnabledHeroesAtLimit(cfg, st)) {
            return resp("stop_blood_war", "所有启用武将已达推城上限，准备停止血战")
        }

        if (!yolo.ready) {
            return resp("error", "YOLO 未就绪: ${yolo.loadError ?: "未知"}")
        }

        val dets = YoloScreenMapper.detectOnScreen(yolo, bitmap, yoloConf)

        tryGlobalClose(dets, cxOff, cyOff, currentStep)?.let { return it.withDets(dets) }

        val result = when (currentStep) {
            "init" -> stepInit(dets)
            "navigate_map" -> stepNavigateMap(dets, cxOff, cyOff)
            "map_opened" -> stepMapOpened(dets)
            "click_city" -> stepClickCity(dets, cfg, st, fw, fh)
            "after_city_click" -> stepAfterCityClick(dets, cfg, st, fw, fh, cxOff, cyOff)
            "blood_battle_nav" -> stepBloodBattleNav(dets, cfg, st, fw, fh, cxOff, cyOff)
            "click_xuezhan" -> resp("scan_setup", "进入血战设置")
            "scan_setup" -> stepScanSetup(dets, bitmap, cfg, st, cxOff, cyOff)
            "minimize" -> stepMinimize(dets, cxOff, cyOff)
            "after_minimize" -> stepAfterMinimize(dets, cxOff, cyOff)
            "wait_guozhan" -> stepWaitGuozhan(dets, bitmap, cfg, st, fw, fh, cxOff, cyOff)
            "guozhan_battle" -> stepGuozhanBattle(dets, bitmap, cfg, st, fw, fh, cxOff, cyOff)
            "stop_blood_war" -> stepStopBloodWar(dets, st, cxOff, cyOff)
            "error" -> resp("init", "从 error 恢复")
            else -> resp("init", "未知 step=$currentStep，重置")
        }
        fixedPointClicks = result.fixedPointClicks
        activeHeroName = result.activeHeroName
        activeHeroSlot = result.activeHeroSlot
        if (result.huanyeClicks > 0) {
            huanyeClicks = result.huanyeClicks
        } else if (result.step == "click_xuezhan") {
            huanyeClicks = 0
        }
        return result.withDets(dets)
    }

    private fun FlowResult.withDets(dets: List<YoloDetection>) = copy(detections = dets)

    private fun stepInit(dets: List<YoloDetection>): FlowResult {
        if (worldMapOpen(dets)) {
            return resp("click_city", "已处于世界地图（识别「武将」），准备点城")
        }
        if (findBest(dets, "主城") != null) {
            return resp("navigate_map", "检测到「主城」，进入地图导航")
        }
        if (findBest(dets, "地图") != null) {
            return resp("navigate_map", "未检测到主城，尝试继续导航")
        }
        return resp("init", "等待「主城」界面")
    }

    private fun stepNavigateMap(dets: List<YoloDetection>, cxOff: Int, cyOff: Int): FlowResult {
        val mapBtn = findBest(dets, "地图")
        if (mapBtn != null) {
            val (tx, ty) = detCenterFull(mapBtn, cxOff, cyOff)
            return resp("map_opened", "点击「地图」", listOf(FlowClick(tx, ty)))
        }
        if (findBest(dets, "主城") != null) {
            return resp("navigate_map", "仍在主城，等待「地图」按钮")
        }
        return FlowResult(
            step = "map_opened",
            message = "未找到地图按钮，尝试直接点城",
            nextStep = "map_opened",
        )
    }

    private fun stepMapOpened(dets: List<YoloDetection>): FlowResult {
        if (worldMapOpen(dets)) {
            return resp("click_city", "世界地图已打开（识别「武将」），准备点城")
        }
        if (findBest(dets, "主城") != null) {
            return resp("map_opened", "等待世界地图加载（识别「武将」）")
        }
        return resp("map_opened", "等待世界地图界面")
    }

    private fun stepClickCity(
        dets: List<YoloDetection>,
        cfg: SaochengConfig,
        st: SaochengState,
        fw: Int,
        fh: Int,
    ): FlowResult {
        if (!worldMapOpen(dets)) {
            if (findBest(dets, "主城") != null) {
                return resp("click_city", "世界地图加载中（等待「武将」）…")
            }
            return resp("click_city", "等待世界地图（识别「武将」）")
        }
        if (findBest(dets, "血战") != null || findBest(dets, "换页") != null) {
            return resp("after_city_click", "已在主城血战面板，跳过点城")
        }
        return clickConfiguredCity(cfg, st, fw, fh, null)
    }

    private fun stepAfterCityClick(
        dets: List<YoloDetection>,
        cfg: SaochengConfig,
        st: SaochengState,
        fw: Int,
        fh: Int,
        cxOff: Int,
        cyOff: Int,
    ): FlowResult {
        if (worldMapOpen(dets)) {
            return clickConfiguredCity(cfg, st, fw, fh, "仍在世界地图，再次点击城池")
        }
        if (findBest(dets, "血战") != null || findBest(dets, "换页") != null) {
            return FlowResult(
                step = "blood_battle_nav",
                message = "换页/血战已出现，进入导航",
                nextStep = "blood_battle_nav",
                fixedPointClicks = 0,
            )
        }
        if (fixedPointClicks < FlowConstants.MAX_FIXED_POINT_CLICKS) {
            val (px, py) = ScreenCoord.scalePoint(
                FlowConstants.BLOOD_BATTLE_OPEN_BTN.first.toFloat(),
                FlowConstants.BLOOD_BATTLE_OPEN_BTN.second.toFloat(),
                fw, fh,
            )
            val n = fixedPointClicks + 1
            return FlowResult(
                step = "after_city_click",
                message = "点击固定点 (${FlowConstants.BLOOD_BATTLE_OPEN_BTN.first},${FlowConstants.BLOOD_BATTLE_OPEN_BTN.second}) ($n/${FlowConstants.MAX_FIXED_POINT_CLICKS})",
                clicks = listOf(FlowClick(px, py)),
                nextStep = "after_city_click",
                fixedPointClicks = n,
            )
        }
        val cityDet = findCityDetCenterOutward(dets, fw / 2, fh / 2)
        if (cityDet != null) {
            val (tx, ty) = detCenterFull(cityDet, cxOff, cyOff)
            return FlowResult(
                step = "blood_battle_nav",
                message = "固定点${FlowConstants.MAX_FIXED_POINT_CLICKS}次未果，点击距中心最近「城池」(${String.format("%.2f", cityDet.confidence)})",
                clicks = listOf(FlowClick(tx, ty)),
                nextStep = "blood_battle_nav",
                fixedPointClicks = 0,
            )
        }
        return FlowResult(
            step = "after_city_click",
            message = "固定点已试${FlowConstants.MAX_FIXED_POINT_CLICKS}次，未识别换页/血战且无城池",
            nextStep = "after_city_click",
            fixedPointClicks = fixedPointClicks,
        )
    }

    private fun stepBloodBattleNav(
        dets: List<YoloDetection>,
        cfg: SaochengConfig,
        st: SaochengState,
        fw: Int,
        fh: Int,
        cxOff: Int,
        cyOff: Int,
    ): FlowResult {
        if (worldMapOpen(dets)) {
            return clickConfiguredCity(cfg, st, fw, fh, "误在世界地图，点击所选城池")
        }
        val xuezhan = findBest(dets, "血战")
        if (xuezhan != null) {
            val (tx, ty) = detCenterFull(xuezhan, cxOff, cyOff)
            huanyeClicks = 0
            return resp("click_xuezhan", "点击「血战」", listOf(FlowClick(tx, ty)))
        }
        val huanye = findBest(dets, "换页")
        if (huanye != null && huanyeClicks < FlowConstants.MAX_HUANYE_CLICKS) {
            val (tx, ty) = detCenterFull(huanye, cxOff, cyOff)
            huanyeClicks++
            return FlowResult(
                step = "blood_battle_nav",
                message = "点击「换页」($huanyeClicks/${FlowConstants.MAX_HUANYE_CLICKS})",
                clicks = listOf(FlowClick(tx, ty)),
                huanyeClicks = huanyeClicks,
            )
        }
        return resp("blood_battle_nav", "等待「血战」或「换页」")
    }

    private suspend fun stepScanSetup(
        dets: List<YoloDetection>,
        bitmap: Bitmap,
        cfg: SaochengConfig,
        st: SaochengState,
        cxOff: Int,
        cyOff: Int,
    ): FlowResult {
        val heroesCfg = store.enabledHeroes(cfg, st)
        if (heroesCfg.isEmpty()) {
            return resp("error", "无可用武将（未启用或已达推城上限）")
        }

        if (!scanModeActive(dets)) {
            val saocheng = findBest(dets, "扫城")
            if (saocheng != null && saocheng.confidence >= 0.30f) {
                val (tx, ty) = detCenterFull(saocheng, cxOff, cyOff)
                return resp("scan_setup", "点击「扫城」切换为扫城中", listOf(FlowClick(tx, ty)))
            }
        }

        if (configuredHeroesReady(dets, heroesCfg)) {
            val dispatchBtn = findDispatchBtn(dets, bitmap, ocr)
            if (dispatchBtn != null) {
                val (tx, ty) = detCenterFull(dispatchBtn, cxOff, cyOff)
                store.advanceCity(st, cfg)
                return resp("click_dispatch", "点击「出兵」", listOf(FlowClick(tx, ty)))
            }
        }

        val heroClicks = buildHeroAdjustmentClicks(dets, heroesCfg, cxOff, cyOff)
        if (heroClicks.isNotEmpty()) {
            return resp("scan_setup", "调整武将选中", heroClicks)
        }

        val dispatchBtn = findDispatchBtn(dets, bitmap, ocr)
        if (dispatchBtn != null) {
            val (tx, ty) = detCenterFull(dispatchBtn, cxOff, cyOff)
            store.advanceCity(st, cfg)
            return resp("click_dispatch", "点击「出兵」", listOf(FlowClick(tx, ty)))
        }

        if (!scanModeActive(dets)) {
            return resp("scan_setup", "等待「扫城」按钮出现")
        }
        return resp("scan_setup", "等待选将完成 / 「出兵」按钮")
    }

    private fun scanModeActive(dets: List<YoloDetection>): Boolean {
        val d = findBest(dets, "扫城-选中") ?: return false
        return d.confidence >= 0.30f
    }

    private fun configuredHeroesReady(dets: List<YoloDetection>, heroesCfg: List<HeroConfig>): Boolean {
        val selectedMarks = findAll(dets, "武将-选中")
        val visible = heroesCfg.mapNotNull { findBest(dets, it.name) }
        if (visible.isEmpty()) return false
        return visible.all { heroIsSelected(it, selectedMarks) }
    }

    private fun buildHeroAdjustmentClicks(
        dets: List<YoloDetection>,
        heroesCfg: List<HeroConfig>,
        cxOff: Int,
        cyOff: Int,
    ): List<FlowClick> {
        if (configuredHeroesReady(dets, heroesCfg)) return emptyList()

        val selectedMarks = findAll(dets, "武将-选中")
        val clicks = mutableListOf<FlowClick>()
        for (hc in heroesCfg) {
            val d = findBest(dets, hc.name) ?: continue
            if (!heroIsSelected(d, selectedMarks)) {
                val (tx, ty) = detCenterFull(d, cxOff, cyOff)
                clicks.add(FlowClick(tx, ty))
            }
        }
        return clicks
    }

    private suspend fun findDispatchBtn(
        dets: List<YoloDetection>,
        bitmap: Bitmap,
        ocr: OcrHelper,
    ): YoloDetection? {
        val d = findBest(dets, "出兵")
        if (d != null && d.confidence >= 0.30f) return d
        for (det in dets) {
            if (det.className in FlowConstants.HERO_CLASS_NAMES) continue
            val txt = ocr.recognizeRegion(bitmap, det.x1, det.y1, det.x2, det.y2, pad = 2)
            if ("出兵" in txt) return det
        }
        return null
    }

    private fun stepMinimize(dets: List<YoloDetection>, cxOff: Int, cyOff: Int): FlowResult {
        val mini = findBest(dets, "最小化")
        if (mini != null) {
            val (tx, ty) = detCenterFull(mini, cxOff, cyOff)
            return resp("after_minimize", "点击「最小化」", listOf(FlowClick(tx, ty)))
        }
        return resp("minimize", "等待「最小化」按钮")
    }

    private fun stepAfterMinimize(dets: List<YoloDetection>, cxOff: Int, cyOff: Int): FlowResult {
        val expand = findBest(dets, "血战-展开")
        if (expand != null) {
            val (tx, ty) = detCenterFull(expand, cxOff, cyOff)
            return resp("wait_guozhan", "点击「血战-展开」", listOf(FlowClick(tx, ty)))
        }
        if (hasClass(dets, "国战中") || findBest(dets, "血战-关闭") != null) {
            return resp("wait_guozhan", "血战面板已展开，等待国战")
        }
        return resp("after_minimize", "等待「血战-展开」")
    }

    private suspend fun stepWaitGuozhan(
        dets: List<YoloDetection>,
        bitmap: Bitmap,
        cfg: SaochengConfig,
        st: SaochengState,
        fw: Int,
        fh: Int,
        cxOff: Int,
        cyOff: Int,
    ): FlowResult {
        val heroesCfg = store.enabledHeroes(cfg, st)
        val heroNames = heroesCfg.map { it.name }
        val slots = mutableListOf<Int>()
        if (cfg.playerName.isNotBlank()) {
            GuozhanHelper.findPlayerHeroSlot(bitmap, ocr, cfg.playerName, fw, fh, cxOff, cyOff)?.let { slots.add(it) }
        }
        for (s in 1..5) if (s !in slots) slots.add(s)

        for (slot in slots) {
            if (cfg.playerName.isNotBlank() && !GuozhanHelper.slotPlayerNameMatches(bitmap, ocr, cfg.playerName, slot, fw, fh, cxOff, cyOff)) {
                continue
            }
            if (GuozhanHelper.guozhanNearSlot(dets, slot, fw, fh, cxOff, cyOff, bitmap.width, bitmap.height) == null) continue
            val heroName = GuozhanHelper.heroClassForSlot(dets, heroNames, slot, fw, fh, cxOff, cyOff, bitmap.width, bitmap.height)
                ?: activeHeroName
            val (tx, ty) = heroStatusCenterFull(slot, fw, fh)
            return FlowResult(
                step = "guozhan_battle",
                message = "槽位$slot「国战中」(${heroName.ifBlank { "?" }})，点击进入",
                clicks = listOf(FlowClick(tx, ty)),
                nextStep = "guozhan_battle",
                activeHeroName = heroName,
                activeHeroSlot = slot,
            )
        }
        return resp("wait_guozhan", "等待配置武将「国战中」")
    }

    private suspend fun stepGuozhanBattle(
        dets: List<YoloDetection>,
        bitmap: Bitmap,
        cfg: SaochengConfig,
        st: SaochengState,
        fw: Int,
        fh: Int,
        cxOff: Int,
        cyOff: Int,
    ): FlowResult {
        val heroesCfg = store.enabledHeroes(cfg, st)
        val heroNames = heroesCfg.map { it.name }
        val victory = findBest(dets, "胜利")
        if (victory != null) {
            var pushHero: String? = null
            if (activeHeroSlot > 0) {
                if (GuozhanHelper.slotPlayerNameMatches(bitmap, ocr, cfg.playerName, activeHeroSlot, fw, fh, cxOff, cyOff)) {
                    pushHero = activeHeroName.ifBlank {
                        GuozhanHelper.heroClassForSlot(dets, heroNames, activeHeroSlot, fw, fh, cxOff, cyOff, bitmap.width, bitmap.height)
                    }
                }
            } else if (cfg.playerName.isNotBlank()) {
                val ps = GuozhanHelper.findPlayerHeroSlot(bitmap, ocr, cfg.playerName, fw, fh, cxOff, cyOff)
                if (ps != null) {
                    pushHero = GuozhanHelper.heroClassForSlot(dets, heroNames, ps, fw, fh, cxOff, cyOff, bitmap.width, bitmap.height)
                }
            } else {
                pushHero = activeHeroName.ifBlank { heroNames.firstOrNull() }
            }
            val msg = if (pushHero != null) {
                store.recordHeroPush(st, pushHero)
                "$pushHero 推城+1"
            } else {
                "角色名不匹配，未计推城"
            }
            if (store.allEnabledHeroesAtLimit(cfg, st)) {
                return FlowResult(
                    step = "stop_blood_war",
                    message = "胜利！$msg，全部武将达上限，停止血战",
                    nextStep = "stop_blood_war",
                    activeHeroName = "",
                    activeHeroSlot = 0,
                )
            }
            return FlowResult(
                step = "after_minimize",
                message = "胜利！$msg，返回监控",
                nextStep = "after_minimize",
                activeHeroName = "",
                activeHeroSlot = 0,
            )
        }

        val (myArmy, enemyArmy) = GuozhanHelper.parseArmyCountsAsync(bitmap, ocr, fw, fh, cxOff, cyOff)

        if (!hasClass(dets, "国战中") && !hasClass(dets, "单挑")) {
            if (myArmy == 0 && enemyArmy == 0) {
                return resp("after_minimize", "已离开国战界面")
            }
        }

        val dantiao = findBest(dets, "单挑")
        if (myArmy > 3 && dantiao != null) {
            val (tx, ty) = detCenterFull(dantiao, cxOff, cyOff)
            return resp("guozhan_battle", "我军$myArmy>3，点击「单挑」", listOf(FlowClick(tx, ty)))
        }

        val kuaijin = findBest(dets, "快进")
        if (kuaijin != null) {
            val (tx, ty) = detCenterFull(kuaijin, cxOff, cyOff)
            return resp("guozhan_battle", "点击「快进」", listOf(FlowClick(tx, ty)))
        }

        if (hasClass(dets, "国战中")) {
            return resp("guozhan_battle", "国战中 我军=$myArmy 敌军=$enemyArmy，等待快进/胜利")
        }
        return resp("after_minimize", "国战结束，返回主界面监控")
    }

    private fun stepStopBloodWar(
        dets: List<YoloDetection>,
        st: SaochengState,
        cxOff: Int,
        cyOff: Int,
    ): FlowResult {
        val xuezhanClose = findBest(dets, "血战-关闭")
        if (xuezhanClose != null) {
            val (tx, ty) = detCenterFull(xuezhanClose, cxOff, cyOff)
            return resp("stop_blood_war", "点击「血战-关闭」", listOf(FlowClick(tx, ty)))
        }
        val stopBtn = findBest(dets, "停止血战")
        if (stopBtn != null) {
            val (tx, ty) = detCenterFull(stopBtn, cxOff, cyOff)
            return resp("stop_blood_war", "点击「停止血战」", listOf(FlowClick(tx, ty)))
        }
        val confirm = findBest(dets, "确定")
        if (confirm != null) {
            val (tx, ty) = detCenterFull(confirm, cxOff, cyOff)
            store.startWaitNextHour(st)
            return resp("wait_next_hour", "点击「确定」，等待下一个整点", listOf(FlowClick(tx, ty)))
        }
        if (findBest(dets, "主城") != null) {
            store.startWaitNextHour(st)
            return resp("wait_next_hour", "已在主城，等待下一个整点")
        }
        return resp("stop_blood_war", "等待「血战-关闭」/「停止血战」/「确定」")
    }

    private fun findCityDetCenterOutward(
        dets: List<YoloDetection>,
        centerX: Int,
        centerY: Int,
        minConf: Float = 0.30f,
    ): YoloDetection? {
        val cands = dets.filter { it.className == "城池" && it.confidence >= minConf }
        if (cands.isEmpty()) return null
        return cands.minByOrNull {
            val dx = it.centerX - centerX
            val dy = it.centerY - centerY
            dx * dx + dy * dy
        }
    }

    private fun worldMapOpen(dets: List<YoloDetection>): Boolean {
        val d = findBest(dets, "武将") ?: return false
        return d.confidence >= 0.25f
    }

    private fun clickConfiguredCity(
        cfg: SaochengConfig,
        st: SaochengState,
        fw: Int,
        fh: Int,
        message: String?,
    ): FlowResult {
        val cid = store.nextCityId(cfg, st)
            ?: return resp("error", "未配置扫城城池（请在悬浮窗选择城池）")
        val (sx, sy) = CityData.scaleCityScreenXY(cid, fw, fh)
        val name = CityData.get(cid)?.name ?: cid.toString()
        val msg = message ?: "点击城池 #$cid $name"
        fixedPointClicks = 0
        return FlowResult(
            step = "after_city_click",
            message = msg,
            clicks = listOf(FlowClick(sx, sy)),
            nextStep = "after_city_click",
            fixedPointClicks = 0,
        )
    }

    private fun tryGlobalClose(dets: List<YoloDetection>, cxOff: Int, cyOff: Int, step: String): FlowResult? {
        if (step in setOf("map_opened", "click_city", "after_city_click", "blood_battle_nav")) return null
        if (worldMapOpen(dets)) return null
        if (step != "init") return null
        if (findBest(dets, "主城") != null || findBest(dets, "血战") != null || findBest(dets, "换页") != null) {
            return null
        }
        for (name in listOf("叉", "关闭")) {
            val d = findBest(dets, name) ?: continue
            if (d.confidence >= 0.5f) {
                val (tx, ty) = detCenterFull(d, cxOff, cyOff)
                return resp("init", "全局：点击 $name", listOf(FlowClick(tx, ty)))
            }
        }
        return null
    }

    private fun heroIsSelected(hero: YoloDetection, selectedMarks: List<YoloDetection>): Boolean {
        val markX = hero.x1 + 4
        val markY = hero.y1 + 4
        for (m in selectedMarks) {
            if (m.containsPoint(markX, markY, FlowConstants.HERO_SELECT_MARK_MARGIN)) return true
            if (hero.iouWith(m) > 0.05f) return true
        }
        return false
    }

    private fun heroStatusCenterFull(heroIndex: Int, fw: Int, fh: Int): Pair<Int, Int> {
        val base = FlowConstants.STATUS_REGION_BY_HERO[heroIndex] ?: FlowConstants.STATUS_REGION_BY_HERO[1]!!
        val cx = (base[0] + base[2]) / 2
        val cy = (base[1] + base[3]) / 2
        return ScreenCoord.scalePoint(cx.toFloat(), cy.toFloat(), fw, fh)
    }

    private fun detCenterFull(det: YoloDetection, cxOff: Int, cyOff: Int): Pair<Int, Int> {
        return det.centerX + cxOff to det.centerY + cyOff
    }

    private fun resp(step: String, message: String, clicks: List<FlowClick> = emptyList()): FlowResult {
        val next = SAOCHENG_NEXT_STEP[step] ?: step
        return FlowResult(step = step, message = message, clicks = clicks, nextStep = next, huanyeClicks = huanyeClicks, fixedPointClicks = fixedPointClicks, activeHeroName = activeHeroName, activeHeroSlot = activeHeroSlot)
    }

    companion object {
        val SAOCHENG_NEXT_STEP = mapOf(
            "init" to "init",
            "navigate_map" to "navigate_map",
            "map_opened" to "map_opened",
            "click_city" to "click_city",
            "after_city_click" to "after_city_click",
            "blood_battle_nav" to "blood_battle_nav",
            "click_xuezhan" to "scan_setup",
            "scan_setup" to "scan_setup",
            "click_dispatch" to "minimize",
            "minimize" to "minimize",
            "after_minimize" to "after_minimize",
            "wait_guozhan" to "wait_guozhan",
            "guozhan_battle" to "guozhan_battle",
            "stop_blood_war" to "stop_blood_war",
            "wait_next_hour" to "wait_next_hour",
            "error" to "init",
        )
    }
}
