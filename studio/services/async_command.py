"""在 Qt 事件循环中异步执行子进程，避免阻塞 Studio 界面。"""

from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, Signal


class AsyncCommand(QObject):
    """包装 QProcess：合并 stdout/stderr，按块发出 output 信号。"""

    output = Signal(str)
    finished = Signal(int)  # exit code

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._on_read)
        self._proc.finished.connect(self._on_finished)
        self._pending = ""

    def is_running(self) -> bool:
        return self._proc.state() != QProcess.ProcessState.NotRunning

    def start(self, program: str, args: list[str], *, cwd: str | None = None) -> bool:
        if self.is_running():
            return False
        self._pending = ""
        if cwd:
            self._proc.setWorkingDirectory(cwd)
        self._proc.start(program, args)
        return self._proc.waitForStarted(5000)

    def kill(self) -> None:
        if self.is_running():
            self._proc.kill()

    def _on_read(self) -> None:
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        if not data:
            return
        text = self._pending + data
        lines = text.splitlines()
        if text.endswith("\n") or text.endswith("\r"):
            self._pending = ""
        else:
            self._pending = lines.pop() if lines else text
        for line in lines:
            self.output.emit(line.rstrip("\r"))
        if self._pending and not lines:
            return

    def _on_finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        if self._pending.strip():
            self.output.emit(self._pending.rstrip("\r"))
        self._pending = ""
        self.finished.emit(int(code))
