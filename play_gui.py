"""《双生纹》图形版：python3 play_gui.py

需要先安装 pygame：python3 -m pip install pygame-ce
"""

if __name__ == "__main__":
    from startup import prepare_environment
    prepare_environment()

from shuangshengwen.gui.app import main

if __name__ == "__main__":
    main()
    from startup import pause_if_double_clicked
    pause_if_double_clicked()

