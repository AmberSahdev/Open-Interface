import ctypes
from typing import Any

import pyautogui
from PIL import Image

from platform_support.detector import get_platform_name


class ScreenAdapter:
    _runtime_initialized = False

    def __init__(self, platform_name: str | None = None):
        if platform_name is None:
            platform_name = get_platform_name()
        self.platform_name = platform_name

    def initialize_runtime(self) -> None:
        if ScreenAdapter._runtime_initialized:
            return
        ScreenAdapter._runtime_initialized = True

        if self.platform_name != 'windows':
            return

        self._enable_windows_dpi_awareness()

    def get_size(self) -> tuple[int, int]:
        self.initialize_runtime()
        screen_width, screen_height = pyautogui.size()
        return int(screen_width), int(screen_height)

    def get_screenshot(self) -> Image.Image:
        self.initialize_runtime()
        screenshot = pyautogui.screenshot()
        return screenshot

    def build_capture_metrics(self) -> dict[str, Any]:
        screenshot = self.get_screenshot()
        logical_width, logical_height = self.get_size()
        return {
            'logical_screen': {
                'width': logical_width,
                'height': logical_height,
            },
            'captured_screen': {
                'width': screenshot.width,
                'height': screenshot.height,
            },
            'image': screenshot,
        }

    def _enable_windows_dpi_awareness(self) -> None:
        try:
            user32 = ctypes.windll.user32
        except Exception as exc:
            print(f'Warning: user32 is unavailable for DPI awareness setup: {exc}')
            return

        shcore = None
        try:
            shcore = ctypes.windll.shcore
        except Exception:
            shcore = None

        if shcore is not None:
            try:
                process_per_monitor_dpi_aware = 2
                shcore.SetProcessDpiAwareness(process_per_monitor_dpi_aware)
                return
            except Exception as exc:
                print(f'Warning: SetProcessDpiAwareness failed: {exc}')

        try:
            user32.SetProcessDPIAware()
        except Exception as exc:
            print(f'Warning: SetProcessDPIAware failed: {exc}')


def initialize_platform_runtime() -> None:
    ScreenAdapter().initialize_runtime()
