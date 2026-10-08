"""Unified launcher: GUI by default, --cli for console, --check for diagnostics."""
import argparse
from startup import check_runtime, pause_if_double_clicked, prepare_environment


def main(argv=None):
    parser = argparse.ArgumentParser(description="双生纹启动器", add_help=False)
    parser.add_argument("--cli", action="store_true")
    parser.add_argument("--check", action="store_true")
    options, remaining = parser.parse_known_args(argv)
    if options.check:
        check_runtime(gui=not options.cli)
        return
    if options.cli:
        import sys
        from play import main as run
        sys.argv = [sys.argv[0]] + remaining
        run()
    else:
        from shuangshengwen.gui.app import main as run
        run(remaining)


if __name__ == "__main__":
    prepare_environment()
    try:
        main()
    except KeyboardInterrupt:
        print("\n已退出")
    except EOFError:
        print("当前控制台不支持输入。请使用终端运行 start.py --cli，或运行图形版 start.py。")
    pause_if_double_clicked()
