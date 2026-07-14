package com.autoscript.core.overlay

import android.content.Context
import java.io.File
import java.util.zip.CRC32

/**
 * 设备端 layout 覆盖存储：`filesDir/layout-overrides/ui/layout.json`。
 *
 * 加载优先级：
 * 1. 设计模式显式保存的覆盖（带 user_override 标记）
 * 2. APK 内置 assets（**不**读取热更新 project_overlay 中的 layout）
 *
 * APK layout 变更或检测到非用户覆盖的陈旧文件时，自动清理覆盖与热更新 layout 残留。
 */
object LayoutOverrideStore {

    private const val RELATIVE_PATH = "ui/layout.json"
    private const val APK_ASSETS_PATH = "project/ui/layout.json"
    private const val PREFS = "layout_override_meta"
    private const val KEY_APK_LAYOUT_CRC = "apk_layout_crc"
    private const val KEY_USER_OVERRIDE = "user_layout_override"

    enum class LoadSource {
        APK,
        USER_OVERRIDE,
        APK_MISSING,
    }

    data class LoadResult(
        val config: LayoutConfig,
        val source: LoadSource,
    )

    fun overrideFile(context: Context): File =
        File(context.filesDir, "layout-overrides/$RELATIVE_PATH")

    fun load(context: Context): LayoutConfig = loadWithMeta(context).config

    fun loadWithMeta(context: Context): LoadResult {
        purgeStaleLayoutCaches(context)
        val apkText = apkLayoutText(context)
        if (apkText == null) {
            com.autoscript.core.log.ScriptLog.w(
                "layout.json 未打入 APK（assets/$APK_ASSETS_PATH），使用内置默认界面",
            )
            return LoadResult(LayoutConfig.DEFAULT.normalizedForRuntime(), LoadSource.APK_MISSING)
        }
        val apkCfg = runCatching {
            LayoutConfig.parse(apkText).normalizedForRuntime()
        }.getOrElse { err ->
            com.autoscript.core.log.ScriptLog.w(
                "layout.json 解析失败，使用内置默认界面: ${err.message}",
            )
            return LoadResult(LayoutConfig.DEFAULT.normalizedForRuntime(), LoadSource.APK_MISSING)
        }

        val override = overrideFile(context)
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val userOverride = prefs.getBoolean(KEY_USER_OVERRIDE, false)
        if (override.isFile && userOverride) {
            val cfg = runCatching {
                LayoutConfig.parse(override.readText()).normalizedForRuntime()
            }.getOrElse {
                com.autoscript.core.log.ScriptLog.w("设备 layout 覆盖解析失败，回退 APK 内置 layout")
                apkCfg
            }
            return LoadResult(cfg, LoadSource.USER_OVERRIDE)
        }
        if (override.isFile) {
            override.delete()
        }
        return LoadResult(apkCfg, LoadSource.APK)
    }

    fun save(context: Context, layout: LayoutConfig): File {
        val file = overrideFile(context)
        file.parentFile?.mkdirs()
        file.writeText(LayoutJsonWriter.toJson(layout))
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_USER_OVERRIDE, true)
            .apply()
        return file
    }

    fun hasOverride(context: Context): Boolean = overrideFile(context).isFile

    fun clear(context: Context): Boolean {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .remove(KEY_USER_OVERRIDE)
            .apply()
        return overrideFile(context).delete()
    }

    /** APK 更新或热更新 layout 残留时，清理非用户覆盖。 */
    private fun purgeStaleLayoutCaches(context: Context) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val apkText = apkLayoutText(context)
        val apkCrc = if (apkText != null) crcOf(apkText) else 0L
        val recorded = prefs.getLong(KEY_APK_LAYOUT_CRC, -1L)
        val apkChanged = recorded != apkCrc

        if (apkChanged) {
            overrideFile(context).delete()
            prefs.edit()
                .putLong(KEY_APK_LAYOUT_CRC, apkCrc)
                .remove(KEY_USER_OVERRIDE)
                .apply()
        } else if (overrideFile(context).isFile && !prefs.getBoolean(KEY_USER_OVERRIDE, false)) {
            overrideFile(context).delete()
        }

        val hotLayout = File(context.filesDir, "project_overlay/$RELATIVE_PATH")
        if (hotLayout.isFile && (apkChanged || !prefs.getBoolean(KEY_USER_OVERRIDE, false))) {
            hotLayout.delete()
        }
    }

    /** 仅读 APK 内置 layout，跳过热更新 project_overlay。 */
    private fun apkLayoutText(context: Context): String? =
        runCatching {
            context.assets.open(APK_ASSETS_PATH).bufferedReader().use { it.readText() }
        }.getOrNull()

    private fun crcOf(text: String): Long {
        val crc = CRC32()
        crc.update(text.toByteArray(Charsets.UTF_8))
        return crc.value
    }
}
