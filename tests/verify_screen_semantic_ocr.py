import os
import sys
import tempfile
import types
from unittest.mock import patch

from PIL import Image


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP_DIR = os.path.join(ROOT_DIR, 'app')

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


def _install_pyautogui_stub() -> None:
    if 'pyautogui' in sys.modules:
        return

    module = types.ModuleType('pyautogui')
    setattr(module, 'PAUSE', 0)
    setattr(module, 'FAILSAFE', False)
    setattr(module, 'size', lambda: (1600, 900))
    setattr(module, 'position', lambda: (0, 0))
    setattr(module, 'screenshot', lambda *args, **kwargs: Image.new('RGB', (1280, 720), color=(245, 246, 248)))

    def _noop(*args, **kwargs):
        return None

    for name in (
        'moveTo',
        'click',
        'doubleClick',
        'rightClick',
        'dragTo',
        'scroll',
        'hotkey',
        'press',
        'write',
        'keyDown',
        'keyUp',
        'mouseDown',
        'mouseUp',
    ):
        setattr(module, name, _noop)

    sys.modules['pyautogui'] = module


_install_pyautogui_stub()

from utils.screen import Screen, create_ocr_backend


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeSettings:
    def get_dict(self) -> dict[str, bool]:
        return {'save_model_prompt_images': False}

    def get_settings_directory_path(self) -> str:
        return tempfile.gettempdir() + '/'


def verify_screen_payload_is_pure_grid() -> None:
    with patch('utils.screen.Settings', FakeSettings):
        payload = Screen().get_visual_prompt_payload()

    frame_context = payload.get('frame_context') or {}
    assert_true('grid_reference' in frame_context, 'frame_context should include grid_reference.')

    disallowed_context_fields = {
        'anchors',
        'raw_visual_candidates',
        'ocr_text_blocks',
        'semantic_regions',
    }
    leaked_context_fields = [field for field in disallowed_context_fields if field in frame_context]
    assert_true(
        not leaked_context_fields,
        f'legacy OCR/semantic fields must not leak in frame_context: {leaked_context_fields}',
    )

    disallowed_screen_state_fields = {
        'ocr_backend_used',
        'ocr_latency_ms',
        'ocr_text_block_count',
        'text_summary',
        'input_regions',
        'button_regions',
        'window_title_regions',
    }
    screen_state = frame_context.get('screen_state') or {}
    leaked_screen_state_fields = [field for field in disallowed_screen_state_fields if field in screen_state]
    assert_true(
        not leaked_screen_state_fields,
        f'legacy OCR summary fields must not leak in screen_state: {leaked_screen_state_fields}',
    )


def verify_ocr_constructor_is_retired() -> None:
    try:
        create_ocr_backend({})
    except RuntimeError as exc:
        message = str(exc).lower()
        assert_true('removed' in message, 'retired OCR constructor should clearly report removal.')
        return
    raise AssertionError('create_ocr_backend should raise RuntimeError after OCR retirement.')


def main() -> None:
    verify_screen_payload_is_pure_grid()
    verify_ocr_constructor_is_retired()
    print('screen semantic OCR verification retired: pure-grid negative checks passed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'screen semantic OCR verification failed: {exc}')
        sys.exit(1)
    sys.exit(0)
