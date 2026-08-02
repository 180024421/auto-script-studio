package com.autoscript.script.saocheng

object FlowConstants {
    val POPUP_BTN = 666 to 431
    /** 点世界地图城池后，详细地图唤出换页/血战面板（1280×720） */
    val BLOOD_BATTLE_OPEN_BTN = 640 to 400

    val HERO_CLASS_NAMES = setOf("武圣", "长坂之龙", "乱世枭雄", "东吴大帝", "汉末诸侯")
    val DEFAULT_HERO_NAMES = listOf("武圣", "长坂之龙", "乱世枭雄", "东吴大帝", "汉末诸侯")

    val MY_ARMY_COUNT_REGION = intArrayOf(48, 18, 195, 88)
    val ENEMY_ARMY_COUNT_REGION = intArrayOf(1085, 18, 1235, 88)

    val HERO_NAME_REGIONS: Map<Int, IntArray> = mapOf(
        1 to intArrayOf(8, 118, 118, 168),
        2 to intArrayOf(8, 218, 118, 268),
        3 to intArrayOf(8, 318, 118, 368),
        4 to intArrayOf(8, 418, 118, 468),
        5 to intArrayOf(8, 518, 118, 568),
    )

    val STATUS_REGION_BY_HERO: Map<Int, IntArray> = mapOf(
        1 to intArrayOf(67, 127, 103, 160),
        2 to intArrayOf(65, 228, 103, 261),
        3 to intArrayOf(70, 329, 103, 364),
        4 to intArrayOf(71, 431, 103, 464),
        5 to intArrayOf(71, 533, 103, 563),
    )

    const val MAX_HUANYE_CLICKS = 12
    const val MAX_FIXED_POINT_CLICKS = 3
    const val HERO_SELECT_MARK_MARGIN = 28
    const val YOLO_INPUT_SIZE = 640
    const val YOLO_CONF = 0.30f
    const val YOLO_IOU = 0.45f
}
