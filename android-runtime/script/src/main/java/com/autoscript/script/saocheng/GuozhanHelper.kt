package com.autoscript.script.saocheng

import android.graphics.Bitmap

object GuozhanHelper {
    suspend fun parseArmyCountsAsync(
        bitmap: Bitmap,
        ocr: OcrHelper,
        fullW: Int,
        fullH: Int,
        cxOff: Int = 0,
        cyOff: Int = 0,
    ): Pair<Int, Int> {
        val myR = ScreenCoord.scaleLtrb(
            FlowConstants.MY_ARMY_COUNT_REGION[0], FlowConstants.MY_ARMY_COUNT_REGION[1],
            FlowConstants.MY_ARMY_COUNT_REGION[2], FlowConstants.MY_ARMY_COUNT_REGION[3],
            fullW, fullH, cxOff, cyOff, bitmap.width, bitmap.height,
        )
        val enR = ScreenCoord.scaleLtrb(
            FlowConstants.ENEMY_ARMY_COUNT_REGION[0], FlowConstants.ENEMY_ARMY_COUNT_REGION[1],
            FlowConstants.ENEMY_ARMY_COUNT_REGION[2], FlowConstants.ENEMY_ARMY_COUNT_REGION[3],
            fullW, fullH, cxOff, cyOff, bitmap.width, bitmap.height,
        )
        val myTxt = ocr.recognizeRegion(bitmap, myR[0], myR[1], myR[2], myR[3], pad = 4)
        val enTxt = ocr.recognizeRegion(bitmap, enR[0], enR[1], enR[2], enR[3], pad = 4)
        return extractCount(myTxt) to extractCount(enTxt)
    }

    suspend fun findPlayerHeroSlot(
        bitmap: Bitmap,
        ocr: OcrHelper,
        playerName: String,
        fullW: Int,
        fullH: Int,
        cxOff: Int = 0,
        cyOff: Int = 0,
    ): Int? {
        if (playerName.isBlank()) return null
        for ((idx, region) in FlowConstants.HERO_NAME_REGIONS) {
            val r = ScreenCoord.scaleLtrb(
                region[0], region[1], region[2], region[3],
                fullW, fullH, cxOff, cyOff, bitmap.width, bitmap.height,
            )
            val txt = ocr.recognizeRegion(bitmap, r[0], r[1], r[2], r[3], pad = 2)
            if (nameMatches(playerName, txt)) return idx
        }
        return null
    }

    fun nameMatches(configured: String, ocrText: String, minChars: Int = 3): Boolean {
        val a = normalizeName(configured)
        val b = normalizeName(ocrText)
        if (a.isEmpty() || b.isEmpty()) return false
        if (a == b || a in b || b in a) return true
        val n = maxOf(1, minOf(minChars, a.length, b.length))
        if (a.length >= n) {
            for (i in 0..a.length - n) {
                if (a.substring(i, i + n) in b) return true
            }
        }
        if (b.length >= n) {
            for (i in 0..b.length - n) {
                if (b.substring(i, i + n) in a) return true
            }
        }
        return false
    }

    private fun normalizeName(s: String): String =
        s.replace(Regex("[\\s\\u3000·•]"), "")

    suspend fun slotPlayerNameMatches(
        bitmap: Bitmap,
        ocr: OcrHelper,
        playerName: String,
        slot: Int,
        fullW: Int,
        fullH: Int,
        cxOff: Int = 0,
        cyOff: Int = 0,
    ): Boolean {
        if (playerName.isBlank()) return true
        val region = FlowConstants.HERO_NAME_REGIONS[slot] ?: return false
        val r = ScreenCoord.scaleLtrb(
            region[0], region[1], region[2], region[3],
            fullW, fullH, cxOff, cyOff, bitmap.width, bitmap.height,
        )
        val txt = ocr.recognizeRegion(bitmap, r[0], r[1], r[2], r[3], pad = 2)
        return nameMatches(playerName, txt)
    }

    fun heroClassForSlot(
        dets: List<YoloDetection>,
        heroNames: List<String>,
        slot: Int,
        fullW: Int,
        fullH: Int,
        cxOff: Int,
        cyOff: Int,
        imgW: Int,
        imgH: Int,
    ): String? {
        val region = FlowConstants.HERO_NAME_REGIONS[slot] ?: return null
        val r = ScreenCoord.scaleLtrb(
            region[0], region[1], region[2], region[3],
            fullW, fullH, cxOff, cyOff, imgW, imgH,
        )
        val sx = (r[0] + r[2]) / 2
        val sy = (r[1] + r[3]) / 2
        var bestName: String? = null
        var bestD2 = Int.MAX_VALUE
        for (name in heroNames) {
            val d = findBest(dets, name) ?: continue
            val dx = d.centerX - sx
            val dy = d.centerY - sy
            val d2 = dx * dx + dy * dy
            if (d2 < bestD2) {
                bestD2 = d2
                bestName = name
            }
        }
        return if (bestD2 <= 150 * 150) bestName else null
    }

    fun guozhanNearSlot(
        dets: List<YoloDetection>,
        slot: Int,
        fullW: Int,
        fullH: Int,
        cxOff: Int,
        cyOff: Int,
        imgW: Int,
        imgH: Int,
    ): YoloDetection? {
        val region = FlowConstants.HERO_NAME_REGIONS[slot] ?: return null
        val r = ScreenCoord.scaleLtrb(
            region[0], region[1], region[2], region[3],
            fullW, fullH, cxOff, cyOff, imgW, imgH,
        )
        val sx = (r[0] + r[2]) / 2
        val sy = (r[1] + r[3]) / 2
        val all = findAll(dets, "国战中")
        var best: YoloDetection? = null
        var bestD2 = Int.MAX_VALUE
        for (gz in all) {
            val dx = gz.centerX - sx
            val dy = gz.centerY - sy
            val d2 = dx * dx + dy * dy
            if (d2 < bestD2) {
                bestD2 = d2
                best = gz
            }
        }
        return if (bestD2 <= 120 * 120) best else null
    }

    private fun findBest(dets: List<YoloDetection>, name: String): YoloDetection? =
        dets.filter { it.className == name }.maxByOrNull { it.confidence }

    private fun findAll(dets: List<YoloDetection>, name: String): List<YoloDetection> =
        dets.filter { it.className == name }

    private fun extractCount(text: String): Int {
        if (text.isEmpty()) return 0
        val cleaned = text.replace(",", "").replace("，", "")
        val nums = Regex("\\d+").findAll(cleaned).map { it.value.toIntOrNull() ?: 0 }.toList()
        if (nums.isEmpty()) return 0
        val small = nums.filter { it in 1..99 }
        return if (small.isNotEmpty()) small.min() else nums.first()
    }
}
