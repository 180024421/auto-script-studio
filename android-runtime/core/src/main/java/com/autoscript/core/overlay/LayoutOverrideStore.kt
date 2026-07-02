package com.autoscript.core.overlay

import android.content.Context
import com.autoscript.core.project.ProjectAssets
import java.io.File

/**
 * 设备端 layout 覆盖存储：`filesDir/layout-overrides/ui/layout.json`。
 * 加载时优先使用覆盖文件，否则回退到 assets。
 */
object LayoutOverrideStore {

    private const val RELATIVE_PATH = "ui/layout.json"

    fun overrideFile(context: Context): File =
        File(context.filesDir, "layout-overrides/$RELATIVE_PATH")

    fun load(context: Context): LayoutConfig {
        val override = overrideFile(context)
        if (override.isFile) {
            return runCatching {
                LayoutConfig.parse(override.readText())
            }.getOrElse {
                loadFromAssets(context)
            }
        }
        return loadFromAssets(context)
    }

    fun save(context: Context, layout: LayoutConfig): File {
        val file = overrideFile(context)
        file.parentFile?.mkdirs()
        file.writeText(LayoutJsonWriter.toJson(layout))
        return file
    }

    fun hasOverride(context: Context): Boolean = overrideFile(context).isFile

    fun clear(context: Context): Boolean = overrideFile(context).delete()

    private fun loadFromAssets(context: Context): LayoutConfig {
        val assets = ProjectAssets(context)
        return if (assets.exists(RELATIVE_PATH)) {
            LayoutConfig.parse(assets.readYaml(RELATIVE_PATH))
        } else {
            LayoutConfig.DEFAULT
        }
    }
}
