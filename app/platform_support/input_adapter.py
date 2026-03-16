from time import sleep
from typing import Any, cast

import pyautogui

try:
    import Quartz
except Exception:
    Quartz = None

from platform_support.detector import get_platform_name
from platform_support.hotkey_mapper import HotkeyMapper


class InputAdapter:
    MACOS_MULTI_CLICK_FUNCTIONS = {
        'doubleClick': 2,
        'tripleClick': 3,
    }

    def __init__(self, platform_name: str | None = None):
        if platform_name is None:
            platform_name = get_platform_name()
        self.platform_name = platform_name
        self.hotkey_mapper = HotkeyMapper(platform_name)

    def warm_up(self) -> None:
        return None

    def execute(self, function_name: str, parameters: dict[str, Any]) -> None:
        if function_name == 'press':
            self._press(parameters)
            return
        if function_name == 'hotkey':
            self._hotkey(parameters)
            return
        if self._should_use_macos_multi_click(function_name, parameters):
            self._execute_macos_multi_click(function_name, parameters)
            return

        function_to_call = getattr(pyautogui, function_name)
        function_to_call(**parameters)

    def write_text(self, text: str, interval: float) -> None:
        pyautogui.write(text, interval=interval)

    def paste(self) -> None:
        pyautogui.hotkey(*self.hotkey_mapper.get_paste_keys())

    def _press(self, parameters: dict[str, Any]) -> None:
        keys_to_press = parameters.get('keys') or parameters.get('key')
        presses = parameters.get('presses', 1)
        interval = parameters.get('interval', 0.2)

        if isinstance(keys_to_press, list):
            normalized_keys = self.hotkey_mapper.normalize_hotkey_keys(keys_to_press)
            if len(normalized_keys) == 0:
                raise ValueError('press requires at least one valid key.')
            pyautogui.press(normalized_keys, presses=presses, interval=interval)
            return

        normalized_key = self.hotkey_mapper.normalize_key_name(str(keys_to_press or ''))
        if normalized_key == '':
            raise ValueError('press requires a valid key.')
        pyautogui.press(normalized_key, presses=presses, interval=interval)

    def _hotkey(self, parameters: dict[str, Any]) -> None:
        keys_to_press = parameters.get('keys') or parameters.get('key')
        if isinstance(keys_to_press, list):
            normalized_keys = self.hotkey_mapper.normalize_hotkey_keys(keys_to_press)
            if len(normalized_keys) == 0:
                raise ValueError('hotkey requires at least one valid key.')
            pyautogui.hotkey(*normalized_keys)
            return

        if isinstance(keys_to_press, str):
            normalized_key = self.hotkey_mapper.normalize_key_name(keys_to_press, for_hotkey=True)
            if normalized_key == '':
                raise ValueError('hotkey requires a valid key.')
            pyautogui.hotkey(normalized_key)
            return

        normalized_keys = self.hotkey_mapper.normalize_hotkey_keys(
            [str(value or '') for value in parameters.values()]
        )
        if len(normalized_keys) == 0:
            raise ValueError('hotkey requires at least one valid key.')
        pyautogui.hotkey(*normalized_keys)

    def _should_use_macos_multi_click(
        self,
        function_name: str,
        execution_parameters: dict[str, Any],
    ) -> bool:
        if self.platform_name != 'macos' or Quartz is None:
            return False

        if function_name in self.MACOS_MULTI_CLICK_FUNCTIONS:
            return True
        if function_name != 'click':
            return False

        clicks = execution_parameters.get('clicks', 1)
        try:
            return int(clicks) >= 2
        except Exception:
            return False

    def _execute_macos_multi_click(
        self,
        function_name: str,
        execution_parameters: dict[str, Any],
    ) -> None:
        x_value = execution_parameters.get('x')
        y_value = execution_parameters.get('y')
        if x_value is None or y_value is None:
            raise ValueError('macOS multi-click requires resolved x and y coordinates.')

        click_count = self.MACOS_MULTI_CLICK_FUNCTIONS.get(function_name)
        if click_count is None and function_name == 'click':
            click_count = int(execution_parameters.get('clicks', 1))
        if click_count is None or click_count < 2:
            raise ValueError(f'Unsupported macOS multi-click function: {function_name}')

        x = int(float(x_value))
        y = int(float(y_value))
        button = execution_parameters.get('button', 'left')
        interval = float(execution_parameters.get('interval', 0.0))
        duration = float(execution_parameters.get('duration', 0.0))

        mouse_button, down_event_type, up_event_type = self._resolve_macos_mouse_button(button)

        pyautogui.moveTo(x=x, y=y, duration=duration)
        sleep(0.01)

        for click_index in range(1, click_count + 1):
            self._post_macos_click_event(
                event_type=down_event_type,
                x=x,
                y=y,
                mouse_button=mouse_button,
                click_state=click_index,
            )
            self._post_macos_click_event(
                event_type=up_event_type,
                x=x,
                y=y,
                mouse_button=mouse_button,
                click_state=click_index,
            )

            if click_index < click_count and interval > 0.0:
                sleep(interval)

    def _resolve_macos_mouse_button(self, button: Any) -> tuple[int, int, int]:
        if Quartz is None:
            raise RuntimeError('Quartz is unavailable for macOS multi-click handling.')

        quartz = cast(Any, Quartz)
        normalized_button = str(button or 'left').strip().lower()
        if normalized_button in {'left', 'primary', '1'}:
            return (
                getattr(quartz, 'kCGMouseButtonLeft'),
                getattr(quartz, 'kCGEventLeftMouseDown'),
                getattr(quartz, 'kCGEventLeftMouseUp'),
            )
        if normalized_button in {'right', 'secondary', '3'}:
            return (
                getattr(quartz, 'kCGMouseButtonRight'),
                getattr(quartz, 'kCGEventRightMouseDown'),
                getattr(quartz, 'kCGEventRightMouseUp'),
            )
        if normalized_button in {'middle', '2'}:
            return (
                getattr(quartz, 'kCGMouseButtonCenter'),
                getattr(quartz, 'kCGEventOtherMouseDown'),
                getattr(quartz, 'kCGEventOtherMouseUp'),
            )
        raise ValueError(f'Unsupported mouse button for macOS multi-click: {button}')

    def _post_macos_click_event(
        self,
        event_type: int,
        x: int,
        y: int,
        mouse_button: int,
        click_state: int,
    ) -> None:
        if Quartz is None:
            raise RuntimeError('Quartz is unavailable for macOS multi-click handling.')

        quartz = cast(Any, Quartz)
        event = quartz.CGEventCreateMouseEvent(None, event_type, (x, y), mouse_button)
        quartz.CGEventSetIntegerValueField(event, getattr(quartz, 'kCGMouseEventClickState'), click_state)
        quartz.CGEventPost(getattr(quartz, 'kCGHIDEventTap'), event)
