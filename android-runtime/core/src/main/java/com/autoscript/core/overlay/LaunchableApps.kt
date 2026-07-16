package com.autoscript.core.overlay

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager

/** 可启动应用列表，供面板 `options_source: launchable_apps` 使用。 */
object LaunchableApps {

    data class Entry(
        val label: String,
        val packageName: String,
    ) {
        fun displayLabel(): String = label.ifBlank { packageName }
    }

    fun list(context: Context, includePlaceholder: Boolean = true): List<Entry> {
        val pm = context.packageManager
        val main = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        @Suppress("DEPRECATION")
        val activities = pm.queryIntentActivities(main, PackageManager.MATCH_ALL)
        val seen = linkedSetOf<String>()
        val out = mutableListOf<Entry>()
        if (includePlaceholder) {
            out.add(Entry("请选择应用…", ""))
        }
        activities
            .sortedBy { it.loadLabel(pm).toString().lowercase() }
            .forEach { ri ->
                val pkg = ri.activityInfo.packageName
                if (!seen.add(pkg)) return@forEach
                out.add(Entry(ri.loadLabel(pm).toString(), pkg))
            }
        return out
    }
}
