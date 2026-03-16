from platform_support.clipboard_adapter import ClipboardAdapter
from platform_support.detector import get_platform_name
from platform_support.hotkey_mapper import HotkeyMapper
from platform_support.input_adapter import InputAdapter
from platform_support.local_apps import get_installed_apps_sample
from platform_support.screen_adapter import ScreenAdapter
from platform_support.screen_adapter import initialize_platform_runtime

__all__ = [
    'ClipboardAdapter',
    'HotkeyMapper',
    'InputAdapter',
    'ScreenAdapter',
    'get_installed_apps_sample',
    'get_platform_name',
    'initialize_platform_runtime',
]
