package com.autoscript.core.accessibility

import android.graphics.Rect
import android.view.accessibility.AccessibilityNodeInfo

data class A11yNodeHit(
    val text: String,
    val centerX: Int,
    val centerY: Int,
    val bounds: Rect,
    val resourceId: String?,
)

object AccessibilityFinder {

    fun findByText(
        text: String,
        matchMode: String = "contains",
        index: Int = 0,
    ): A11yNodeHit? {
        val svc = AutomationAccessibilityService.get() ?: return null
        val root = svc.rootInActiveWindow ?: return null
        val hits = mutableListOf<A11yNodeHit>()
        collectNodes(root, text, matchMode, hits)
        root.recycle()
        if (hits.isEmpty()) return null
        return hits[index.coerceIn(0, hits.lastIndex)]
    }

    fun findById(resourceId: String, index: Int = 0): A11yNodeHit? {
        val svc = AutomationAccessibilityService.get() ?: return null
        val root = svc.rootInActiveWindow ?: return null
        val hits = mutableListOf<A11yNodeHit>()
        collectById(root, resourceId, hits)
        root.recycle()
        if (hits.isEmpty()) return null
        return hits[index.coerceIn(0, hits.lastIndex)]
    }

    private fun collectNodes(
        node: AccessibilityNodeInfo,
        target: String,
        matchMode: String,
        out: MutableList<A11yNodeHit>,
    ) {
        val texts = listOfNotNull(
            node.text?.toString(),
            node.contentDescription?.toString(),
        ).filter { it.isNotBlank() }
        for (t in texts) {
            if (matches(t, target, matchMode)) {
                out.add(toHit(node, t))
            }
        }
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            collectNodes(child, target, matchMode, out)
            child.recycle()
        }
    }

    private fun collectById(
        node: AccessibilityNodeInfo,
        resourceId: String,
        out: MutableList<A11yNodeHit>,
    ) {
        val id = node.viewIdResourceName
        if (!id.isNullOrBlank() && (id == resourceId || id.endsWith("/$resourceId"))) {
            val label = node.text?.toString().orEmpty().ifBlank { node.contentDescription?.toString().orEmpty() }
            out.add(toHit(node, label.ifBlank { id }))
        }
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            collectById(child, resourceId, out)
            child.recycle()
        }
    }

    private fun matches(text: String, target: String, mode: String): Boolean = when (mode.lowercase()) {
        "equals", "exact" -> text == target
        "startswith" -> text.startsWith(target)
        "endswith" -> text.endsWith(target)
        else -> text.contains(target)
    }

    private fun toHit(node: AccessibilityNodeInfo, text: String): A11yNodeHit {
        val rect = Rect()
        node.getBoundsInScreen(rect)
        return A11yNodeHit(
            text = text,
            centerX = rect.centerX(),
            centerY = rect.centerY(),
            bounds = rect,
            resourceId = node.viewIdResourceName,
        )
    }
}
