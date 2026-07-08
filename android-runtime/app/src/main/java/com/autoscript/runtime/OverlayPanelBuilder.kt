package com.autoscript.runtime

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Typeface
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.view.Gravity
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.SeekBar
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import com.autoscript.core.overlay.OverlayTabButton
import com.autoscript.core.overlay.OverlayTheme
import com.autoscript.core.overlay.OverlayWidgetStore
import com.autoscript.core.overlay.TabConfig
import com.autoscript.core.overlay.WidgetConfig
import com.autoscript.core.overlay.WidgetValidator

/**
 * 将 layout.json 控件渲染为 Android 视图（网格 + 标签页）。
 */
class OverlayPanelBuilder(
    private val context: Context,
    private val theme: OverlayTheme,
    private val onAction: (WidgetConfig) -> Unit,
    private val dp: (Int) -> Int,
    private val designMode: Boolean = false,
    private val designCallbacks: OverlayDesignCallbacks? = null,
    private val widgetPathPrefix: List<Int> = emptyList(),
) {
    /** 自由坐标布局：与 PC 预览一致，标签左、控件右（横向）。 */
    var freeLayoutPlacement: Boolean = false
    fun buildContentGrid(
        widgets: List<WidgetConfig>,
        cols: Int,
        containerPath: List<Int> = emptyList(),
        pathPrefix: List<Int> = widgetPathPrefix,
    ): LinearLayout {
        val grid = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
        }
        var row: LinearLayout? = null
        var colUsed = 0
        widgets.forEachIndexed { index, widget ->
            val span = widget.width.coerceIn(1, cols)
            if (row == null || colUsed + span > cols) {
                row = newRow()
                grid.addView(row)
                colUsed = 0
            }
            val widgetPath = pathPrefix + index
            val inner = buildWidget(widget, cols, widgetPath)
            val cell: View = if (designMode && designCallbacks != null) {
                OverlayDesignFrame(
                    context = context,
                    widgetPath = widgetPath,
                    containerPath = containerPath,
                    indexInContainer = index,
                    containerSize = widgets.size,
                    currentSpan = span,
                    maxCols = cols,
                    callbacks = designCallbacks,
                    dp = dp,
                    content = inner,
                )
            } else {
                inner
            }
            val lp = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, span.toFloat()).apply {
                setMargins(dp(3), dp(3), dp(3), dp(3))
            }
            row!!.addView(cell, lp)
            colUsed += span
            if (colUsed >= cols) {
                row = null
                colUsed = 0
            }
        }
        return grid
    }

    private fun newRow(): LinearLayout = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT,
        )
    }

    @SuppressLint("SetTextI18n")
    fun buildWidget(cfg: WidgetConfig, cols: Int, widgetPath: List<Int>): View = when (cfg.type) {
        "label", "text" -> buildTextDisplay(cfg)
        "input" -> fieldWrap(cfg) {
            EditText(context).apply {
                hint = cfg.placeholder.ifBlank { cfg.label }
                setText(OverlayWidgetStore.get(cfg.id).ifBlank { cfg.default })
                textSize = 12f
                setTextColor(theme.titleText)
                setPadding(dp(4), dp(4), dp(6), dp(4))
                background = theme.logDrawable(dp(6).toFloat())
                isEnabled = !designMode
                addTextChangedListener(object : TextWatcher {
                    override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
                    override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
                    override fun afterTextChanged(s: Editable?) {
                        OverlayWidgetStore.set(cfg.id, s?.toString().orEmpty())
                    }
                })
                setOnFocusChangeListener { _, hasFocus ->
                    if (!hasFocus) {
                        val err = WidgetValidator.validate(cfg, text?.toString().orEmpty())
                        if (err != null) Toast.makeText(context, err, Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }
        "radio" -> fieldWrap(cfg) {
            val opts = cfg.options.ifEmpty { listOf("选项1", "选项2") }
            val group = RadioGroup(context).apply { orientation = RadioGroup.VERTICAL }
            val current = OverlayWidgetStore.get(cfg.id).ifBlank { cfg.default }
            opts.forEach { opt ->
                val rb = RadioButton(context).apply {
                    text = opt
                    textSize = 11f
                    isChecked = opt == current || (current.isBlank() && opt == opts.first())
                    isEnabled = !designMode
                }
                group.addView(rb)
            }
            group.setOnCheckedChangeListener { _, checkedId ->
                val rb = group.findViewById<RadioButton>(checkedId)
                if (rb != null) OverlayWidgetStore.set(cfg.id, rb.text.toString())
            }
            if (current.isNotBlank()) {
                OverlayWidgetStore.set(cfg.id, current)
            } else if (opts.isNotEmpty()) {
                OverlayWidgetStore.set(cfg.id, opts.first())
            }
            group
        }
        "select" -> fieldWrap(cfg) {
            Spinner(context).apply {
                val opts = cfg.options.ifEmpty { listOf("选项1", "选项2") }
                adapter = ArrayAdapter(context, android.R.layout.simple_spinner_dropdown_item, opts)
                val current = OverlayWidgetStore.get(cfg.id).ifBlank { cfg.default }
                val idx = opts.indexOf(current).coerceAtLeast(0)
                setSelection(idx)
                isEnabled = !designMode
                onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
                    override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                        OverlayWidgetStore.set(cfg.id, opts[position])
                    }
                    override fun onNothingSelected(parent: AdapterView<*>?) = Unit
                }
            }
        }
        "multiselect" -> fieldWrap(cfg) {
            val wrap = LinearLayout(context).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            val selected = OverlayWidgetStore.get(cfg.id).ifBlank { cfg.default }
                .split(',').map { it.trim() }.filter { it.isNotEmpty() }.toMutableSet()
            val opts = cfg.options.ifEmpty { listOf("选项A", "选项B") }
            opts.forEach { opt ->
                val cb = CheckBox(context).apply {
                    text = opt
                    textSize = 11f
                    isChecked = opt in selected
                    isEnabled = !designMode
                    setOnCheckedChangeListener { _, checked ->
                        if (checked) selected.add(opt) else selected.remove(opt)
                        OverlayWidgetStore.set(cfg.id, selected.joinToString(","))
                    }
                    layoutParams = LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.WRAP_CONTENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT,
                    ).apply { marginEnd = dp(12) }
                }
                wrap.addView(cb)
            }
            wrap
        }
        "switch" -> fieldWrap(cfg) {
            LinearLayout(context).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.END or Gravity.CENTER_VERTICAL
                addView(android.widget.Switch(context).apply {
                    isChecked = if (OverlayWidgetStore.get(cfg.id).isNotBlank()) {
                        OverlayWidgetStore.isOn(cfg.id)
                    } else {
                        cfg.default.equals("true", true)
                    }
                    isEnabled = !designMode
                    setOnCheckedChangeListener { _, on ->
                        OverlayWidgetStore.set(cfg.id, if (on) "true" else "false")
                    }
                    if (OverlayWidgetStore.get(cfg.id).isBlank()) {
                        OverlayWidgetStore.set(cfg.id, if (isChecked) "true" else "false")
                    }
                })
            }
        }
        "time_range" -> fieldWrap(cfg) {
            val row = LinearLayout(context).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            val start = EditText(context).apply {
                hint = "09:00"
                textSize = 11f
                setTextColor(theme.titleText)
                isEnabled = !designMode
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }
            val end = EditText(context).apply {
                hint = "18:00"
                textSize = 11f
                setTextColor(theme.titleText)
                isEnabled = !designMode
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }
            val raw = OverlayWidgetStore.get(cfg.id).ifBlank { cfg.default }
            if (raw.contains("-")) {
                val p = raw.split("-", limit = 2)
                start.setText(p[0].trim())
                end.setText(p.getOrElse(1) { "" }.trim())
            } else {
                start.setText(cfg.defaultStart.ifBlank { "09:00" })
                end.setText(cfg.defaultEnd.ifBlank { "18:00" })
            }
            fun sync() {
                OverlayWidgetStore.set(cfg.id, "${start.text}-${end.text}")
            }
            start.addTextChangedListener(simpleWatcher { sync() })
            end.addTextChangedListener(simpleWatcher { sync() })
            if (OverlayWidgetStore.get(cfg.id).isBlank()) sync()
            row.addView(TextView(context).apply { text = "从"; textSize = 10f })
            row.addView(start)
            row.addView(TextView(context).apply { text = "到"; textSize = 10f; setPadding(dp(4), 0, dp(4), 0) })
            row.addView(end)
            row
        }
        "slider" -> fieldWrap(cfg) {
            val min = cfg.min?.toInt() ?: 0
            val max = cfg.max?.toInt() ?: 100
            val step = cfg.step.coerceAtLeast(1)
            val cur = OverlayWidgetStore.get(cfg.id).toIntOrNull()
                ?: cfg.default.toIntOrNull() ?: min
            val seek = SeekBar(context).apply {
                this.max = ((max - min) / step).coerceAtLeast(1)
                progress = ((cur - min) / step).coerceIn(0, this.max)
                isEnabled = !designMode
                setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                    override fun onProgressChanged(sb: SeekBar?, progress: Int, fromUser: Boolean) {
                        if (fromUser) OverlayWidgetStore.set(cfg.id, (min + progress * step).toString())
                    }
                    override fun onStartTrackingTouch(sb: SeekBar?) = Unit
                    override fun onStopTrackingTouch(sb: SeekBar?) = Unit
                })
            }
            if (OverlayWidgetStore.get(cfg.id).isBlank()) {
                OverlayWidgetStore.set(cfg.id, (min + seek.progress * step).toString())
            }
            seek
        }
        "stepper" -> fieldWrap(cfg) {
            val min = cfg.min?.toInt() ?: 0
            val max = cfg.max?.toInt() ?: 99
            val step = cfg.step.coerceAtLeast(1)
            var value = OverlayWidgetStore.get(cfg.id).toIntOrNull()
                ?: cfg.default.toIntOrNull() ?: min
            val row = LinearLayout(context).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            val valueTv = TextView(context).apply {
                text = value.toString()
                textSize = 13f
                gravity = Gravity.CENTER
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }
            fun apply(v: Int) {
                value = v.coerceIn(min, max)
                valueTv.text = value.toString()
                OverlayWidgetStore.set(cfg.id, value.toString())
            }
            val minus = Button(context).apply {
                text = "−"
                isAllCaps = false
                isEnabled = !designMode
                setOnClickListener { apply(value - step) }
            }
            val plus = Button(context).apply {
                text = "+"
                isAllCaps = false
                isEnabled = !designMode
                setOnClickListener { apply(value + step) }
            }
            if (OverlayWidgetStore.get(cfg.id).isBlank()) apply(value)
            row.addView(minus)
            row.addView(valueTv)
            row.addView(plus)
            row
        }
        "textarea" -> fieldWrap(cfg) {
            EditText(context).apply {
                hint = cfg.placeholder.ifBlank { cfg.label }
                setText(OverlayWidgetStore.get(cfg.id).ifBlank { cfg.default })
                textSize = 12f
                setTextColor(theme.titleText)
                minLines = cfg.rows.coerceAtLeast(2)
                gravity = Gravity.TOP
                inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
                setPadding(dp(4), dp(4), dp(6), dp(4))
                background = theme.logDrawable(dp(6).toFloat())
                isEnabled = !designMode
                addTextChangedListener(object : TextWatcher {
                    override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
                    override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
                    override fun afterTextChanged(s: Editable?) {
                        OverlayWidgetStore.set(cfg.id, s?.toString().orEmpty())
                    }
                })
            }
        }
        "divider" -> View(context).apply {
            setBackgroundColor(0xFFCBD5E1.toInt())
            minimumHeight = dp(1)
        }
        "tabs" -> buildTabs(cfg, cols, widgetPath)
        else -> makeActionButton(cfg)
    }

    private fun buildTextDisplay(cfg: WidgetConfig): TextView =
        TextView(context).apply {
            text = cfg.text.ifBlank { cfg.label }.ifBlank { "提示文字" }
            val style = cfg.textStyle.lowercase()
            when (style) {
                "title" -> {
                    textSize = 14f
                    setTypeface(typeface, Typeface.BOLD)
                    setTextColor(theme.titleText)
                }
                "hint" -> {
                    textSize = 11f
                    setTextColor(theme.logText)
                }
                else -> {
                    textSize = 12f
                    setTextColor(theme.titleText)
                }
            }
            gravity = when (cfg.align.lowercase()) {
                "center" -> Gravity.CENTER
                "right" -> Gravity.END or Gravity.CENTER_VERTICAL
                else -> Gravity.START or Gravity.CENTER_VERTICAL
            }
            setPadding(dp(8), dp(4), dp(8), dp(4))
            if (freeLayoutPlacement) {
                maxLines = 3
                ellipsize = android.text.TextUtils.TruncateAt.END
            }
        }

    private fun fieldWrap(cfg: WidgetConfig, child: () -> View): LinearLayout =
        LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.MATCH_PARENT,
            )
            setPadding(dp(4), dp(2), dp(4), dp(2))
            if (cfg.label.isNotBlank()) {
                addView(TextView(context).apply {
                    text = cfg.label
                    textSize = 11f
                    setTextColor(theme.titleText)
                    gravity = Gravity.END or Gravity.CENTER_VERTICAL
                    maxWidth = dp(80)
                    minWidth = dp(40)
                    layoutParams = LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.WRAP_CONTENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT,
                    ).apply { marginEnd = dp(4) }
                })
            }
            addView(
                child(),
                LinearLayout.LayoutParams(
                    0,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    1f,
                ),
            )
        }

    private fun buildTabs(cfg: WidgetConfig, cols: Int, tabsWidgetPath: List<Int>): LinearLayout {
        val tabs = cfg.tabs.ifEmpty {
            listOf(
                TabConfig("页签1", emptyList()),
                TabConfig("页签2", emptyList()),
            )
        }
        val wrap = LinearLayout(context).apply { orientation = LinearLayout.VERTICAL }
        val tabBar = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
        }
        val contentHost = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(4), 0, 0)
        }
        wrap.addView(tabBar)
        wrap.addView(contentHost)

        var selected = 0
        fun renderContent() {
            contentHost.removeAllViews()
            val tabContainerPath = tabsWidgetPath + selected
            contentHost.addView(
                buildContentGrid(
                    widgets = tabs[selected].widgets,
                    cols = cols,
                    containerPath = tabContainerPath,
                    pathPrefix = tabContainerPath,
                ),
            )
        }

        tabs.forEachIndexed { index, tab ->
            val btn = OverlayTabButton.create(
                context = context,
                theme = theme,
                title = tab.title,
                selected = index == selected,
                dp = dp,
            ) {
                selected = index
                for (i in 0 until tabBar.childCount) {
                    val child = tabBar.getChildAt(i) as TextView
                    OverlayTabButton.applyStyle(theme, child, i == selected, dp)
                }
                renderContent()
            }
            btn.layoutParams = LinearLayout.LayoutParams(0, dp(34), 1f).apply {
                setMargins(dp(2), 0, dp(2), 0)
            }
            tabBar.addView(btn)
        }
        renderContent()
        return wrap
    }

    private fun makeActionButton(cfg: WidgetConfig): Button =
        Button(context).apply {
            text = actionButtonIcon(cfg)
            textSize = if (cfg.type == "start_script" || cfg.type == "collapse") 18f else 12f
            setTextColor(theme.buttonTextColor(cfg.color))
            isAllCaps = false
            stateListAnimator = null
            elevation = 0f
            minHeight = dp(40)
            background = theme.buttonDrawable(cfg.color, dp(8).toFloat())
            setPadding(dp(4), dp(4), dp(4), dp(4))
            isEnabled = !designMode
            contentDescription = cfg.label.ifBlank { cfg.type }
            setOnClickListener { if (!designMode) onAction(cfg) }
        }

    private fun actionButtonIcon(cfg: WidgetConfig): String = when (cfg.type) {
        "start_script" -> "▶"
        "collapse" -> "▼"
        "tap" -> "⌖"
        "lua", "snippet" -> "{}"
        else -> cfg.label.ifBlank { "●" }
    }

    private fun simpleWatcher(after: () -> Unit): TextWatcher = object : TextWatcher {
        override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
        override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
        override fun afterTextChanged(s: Editable?) { after() }
    }
}
