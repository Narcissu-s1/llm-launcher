"""全局样式交互测试"""

import os
import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSpinBox, QStyle, QStyleOptionSpinBox

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


def test_spinbox增大按钮有足够命中宽度(qt_app):
    """全局样式不应把 spinbox 右侧增大按钮压得过窄"""
    from ui import styles

    spin = QSpinBox()
    spin.setStyleSheet(styles.LIGHT_THEME)
    spin.resize(120, 36)
    spin.show()
    qt_app.processEvents()

    opt = QStyleOptionSpinBox()
    spin.initStyleOption(opt)
    up_rect = spin.style().subControlRect(
        QStyle.ComplexControl.CC_SpinBox,
        opt,
        QStyle.SubControl.SC_SpinBoxUp,
        spin,
    )

    assert up_rect.width() >= 20

    before = spin.value()
    QTest.mouseClick(
        spin,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        up_rect.center(),
    )

    assert spin.value() == before + 1
