package com.autoscript.vision.digit

data class DigitChar(
    val label: String,
    val confidence: Float,
    val x: Int,
    val y: Int,
    val w: Int,
    val h: Int,
)

data class DigitResult(
    val text: String,
    val chars: List<DigitChar>,
    val meanConfidence: Float,
)
