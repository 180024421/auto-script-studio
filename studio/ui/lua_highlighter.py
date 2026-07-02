"""简易 Lua 语法高亮（QSyntaxHighlighter）。"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class LuaHighlighter(QSyntaxHighlighter):
    KEYWORDS = [
        "and",
        "break",
        "do",
        "else",
        "elseif",
        "end",
        "false",
        "for",
        "function",
        "if",
        "in",
        "local",
        "nil",
        "not",
        "or",
        "repeat",
        "return",
        "then",
        "true",
        "until",
        "while",
    ]
    BOT_API = [
        "bot.delay",
        "bot.tap",
        "bot.swipe",
        "bot.longPress",
        "bot.findImage",
        "bot.findColor",
        "bot.findText",
        "bot.findNode",
        "bot.recognizeText",
        "bot.yoloDetect",
        "bot.findYolo",
        "bot.yoloSwipe",
        "bot.log",
        "panel.get",
        "panel.set",
        "panel.is",
        "panel.has",
        "panel.values",
        "panel.watch",
        "panel.unwatch",
        "panel.isOn",
        "panel.getTimeRange",
        "panel.snapshot",
    ]

    def __init__(self, document) -> None:
        super().__init__(document)
        self._rules: list[tuple[re.Pattern[str], QTextCharFormat]] = []

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#0000ff"))
        kw_fmt.setFontWeight(QFont.Bold)
        for w in self.KEYWORDS:
            self._rules.append((re.compile(rf"\b{w}\b"), kw_fmt))

        api_fmt = QTextCharFormat()
        api_fmt.setForeground(QColor("#0d9488"))
        api_fmt.setFontWeight(QFont.DemiBold)
        for api in self.BOT_API:
            self._rules.append((re.compile(re.escape(api)), api_fmt))

        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#a31515"))
        self._rules.append((re.compile(r"'[^'\\]*(?:\\.[^'\\]*)*'"), str_fmt))
        self._rules.append((re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"'), str_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#008000"))
        self._rules.append((re.compile(r"--[^\n]*"), comment_fmt))

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#098658"))
        self._rules.append((re.compile(r"\b\d+(?:\.\d+)?\b"), num_fmt))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)

        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() != 1:
            match = re.search(r"--\[\[", text)
            if match:
                start = match.start()
                self.setCurrentBlockState(1)
        if self.currentBlockState() == 1:
            end = text.find("]]", start)
            comment_fmt = QTextCharFormat()
            comment_fmt.setForeground(QColor("#008000"))
            if end == -1:
                self.setFormat(start, len(text) - start, comment_fmt)
            else:
                self.setFormat(start, end - start + 2, comment_fmt)
                self.setCurrentBlockState(0)
