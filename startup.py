"""Shared startup diagnostics; safe to import before the game dependencies."""
import os
from pathlib import Path
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parent


def launched_by_double_click():
    if os.name != "nt":
        return False
    try:
        import ctypes
        processes = (ctypes.c_ulong * 8)()
        return ctypes.windll.kernel32.GetConsoleProcessList(processes, 8) == 1
    except (AttributeError, OSError):
        return False


def pause_if_double_clicked():
    if launched_by_double_click():
        try:
            input("\n按回车关闭窗口……")
        except (EOFError, OSError):
            pass


def report_error(exc_type, exc, tb):
    details = "".join(traceback.format_exception(exc_type, exc, tb))
    print("\n《双生纹》启动或运行失败，错误信息如下：", file=sys.stderr)
    print(details, file=sys.stderr)
    print("当前 Python：" + sys.executable, file=sys.stderr)
    if isinstance(exc, ModuleNotFoundError):
        print('请在游戏环境执行："' + sys.executable + '" -m pip install -r "' + str(ROOT / 'requirements.txt') + '"', file=sys.stderr)
    log_path = ROOT / "logs" / "startup_error.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(details + "\nPython: " + sys.executable + "\n")
    except OSError:
        log_path = Path(tempfile.gettempdir()) / "shuangshengwen_startup_error.log"
        try:
            with log_path.open("a", encoding="utf-8") as log:
                log.write(details)
        except OSError:
            log_path = None
    if log_path:
        print("错误日志：" + str(log_path), file=sys.stderr)
    print("Windows 推荐双击 start_game.bat；编辑器请选择 cardgame 环境，并在终端/运行控制台启动。", file=sys.stderr)
    pause_if_double_clicked()


def prepare_environment():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.excepthook = report_error
    if sys.version_info < (3, 10):
        raise RuntimeError("需要 Python 3.10 或更新版本，建议使用 conda 的 cardgame 环境（Python 3.12）。")


def check_runtime(gui=True):
    print("Python：" + sys.executable)
    print("版本：" + sys.version.split()[0])
    print("游戏目录：" + str(ROOT))
    if gui:
        import pygame
        print("pygame：" + pygame.version.ver)
    print("启动环境检查通过。")
