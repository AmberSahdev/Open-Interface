from typing import Iterable

from platform_support.detector import get_platform_name


class HotkeyMapper:
    def __init__(self, platform_name: str | None = None):
        if platform_name is None:
            platform_name = get_platform_name()
        self.platform_name = platform_name

    def get_primary_modifier(self) -> str:
        if self.platform_name == 'macos':
            return 'command'
        return 'ctrl'

    def get_paste_keys(self) -> tuple[str, str]:
        return self.get_primary_modifier(), 'v'

    def get_copy_keys(self) -> tuple[str, str]:
        return self.get_primary_modifier(), 'c'

    def get_select_all_keys(self) -> tuple[str, str]:
        return self.get_primary_modifier(), 'a'

    def normalize_key_name(self, key: str, for_hotkey: bool = False) -> str:
        normalized_key = str(key or '').strip().lower()
        if normalized_key == '':
            return normalized_key

        if normalized_key in {'control', 'ctrlleft', 'ctrlright'}:
            return 'ctrl'
        if normalized_key in {'return'}:
            return 'enter'
        if normalized_key in {'escape'}:
            return 'esc'
        if normalized_key in {'arrowleft'}:
            return 'left'
        if normalized_key in {'arrowright'}:
            return 'right'
        if normalized_key in {'arrowup'}:
            return 'up'
        if normalized_key in {'arrowdown'}:
            return 'down'

        if normalized_key in {'cmd', 'command'}:
            if self.platform_name == 'macos':
                return 'command'
            if for_hotkey:
                return self.get_primary_modifier()
            return 'win'

        if normalized_key in {'option', 'optionleft', 'optionright'}:
            if self.platform_name == 'macos':
                return 'option'
            return 'alt'

        if normalized_key in {'meta', 'super'}:
            if self.platform_name == 'macos':
                return 'command'
            return 'win'

        if normalized_key == 'altleft' or normalized_key == 'altright':
            return 'alt'

        return normalized_key

    def normalize_hotkey_keys(self, keys: Iterable[str]) -> list[str]:
        normalized_keys: list[str] = []
        for key in keys:
            normalized_key = self.normalize_key_name(str(key or ''), for_hotkey=True)
            if normalized_key == '':
                continue
            normalized_keys.append(normalized_key)
        return normalized_keys
