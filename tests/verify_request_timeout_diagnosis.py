import os
import sys
import tempfile
from pathlib import Path
from time import perf_counter


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / 'app'

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def install_pyautogui_stub_if_needed() -> None:
    if 'pyautogui' in sys.modules:
        return

    import types

    module = types.ModuleType('pyautogui')
    module.PAUSE = 0
    module.FAILSAFE = False

    def _noop(*args, **kwargs):
        return None

    module.size = lambda: (1920, 1080)
    module.position = lambda: (0, 0)
    for attribute_name in (
        'screenshot',
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
        setattr(module, attribute_name, _noop)

    sys.modules['pyautogui'] = module


def verify_settings_sqlite_persistence() -> None:
    from utils.settings import DEFAULT_REQUEST_TIMEOUT_SECONDS
    from utils.settings import Settings

    with tempfile.TemporaryDirectory() as temp_dir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = temp_dir
        try:
            store = Settings()
            loaded = store.get_dict()
            assert_true(
                'request_timeout_seconds' in loaded,
                'settings 默认配置应包含 request_timeout_seconds。',
            )
            assert_true(
                float(loaded['request_timeout_seconds']) == float(DEFAULT_REQUEST_TIMEOUT_SECONDS),
                'request_timeout_seconds 默认值应为 25 秒。',
            )

            saved = store.save_settings({'request_timeout_seconds': 42.0})
            assert_true(
                float(saved['request_timeout_seconds']) == 42.0,
                '保存后应返回更新后的 request_timeout_seconds。',
            )

            reloaded = Settings().get_dict()
            assert_true(
                float(reloaded['request_timeout_seconds']) == 42.0,
                'request_timeout_seconds 应持久化到 SQLite 并可重新读取。',
            )
        finally:
            if original_home is None:
                os.environ.pop('HOME', None)
            else:
                os.environ['HOME'] = original_home


def verify_model_applies_runtime_timeout() -> None:
    import models.model as model_module

    original_openai = model_module.OpenAI
    created_timeouts = []

    class FakeOpenAI:
        def __init__(self, api_key, base_url, timeout, max_retries):
            created_timeouts.append(float(timeout))
            self.api_key = api_key
            self.base_url = base_url
            self.timeout = timeout
            self.max_retries = max_retries

    model_module.OpenAI = FakeOpenAI

    try:
        model = model_module.Model(
            model_name='fake-model',
            base_url='https://example.invalid/v1/',
            api_key='fake-key',
            context='ctx',
        )

        assert_true(len(created_timeouts) >= 1, 'Model 初始化应创建一次 OpenAI client。')
        assert_true(created_timeouts[-1] == 25.0, 'Model 默认 timeout 应为 25 秒。')

        model.set_runtime_settings({
            'enable_reasoning': False,
            'reasoning_depth': 'low',
            'request_timeout_seconds': 65.0,
        })

        assert_true(created_timeouts[-1] == 65.0, '运行时 settings 应更新 OpenAI client timeout。')

        model.set_runtime_settings({
            'enable_reasoning': False,
            'reasoning_depth': 'low',
            'request_timeout_seconds': 1.0,
        })
        assert_true(created_timeouts[-1] == 25.0, '非法过小 timeout 应回退到默认 25 秒。')
    finally:
        model_module.OpenAI = original_openai


def verify_timeout_error_may_happen_before_full_timeout_window() -> None:
    install_pyautogui_stub_if_needed()
    import core as core_module

    original_llm = core_module.LLM
    original_interpreter = core_module.Interpreter

    with tempfile.TemporaryDirectory() as temp_dir:
        original_home = os.environ.get('HOME')
        os.environ['HOME'] = temp_dir

        class FastTimeoutLLM:
            def __init__(self, *args, **kwargs):
                self.model_name = 'fake-model'
                self.settings_dict = {'base_url': 'https://example.invalid/v1/'}

            def get_instructions_for_objective(self, *args, **kwargs):
                raise TimeoutError('Request timed out.')

            def cleanup(self):
                return None

        class NoopInterpreter:
            def __init__(self, status_queue, session_store=None):
                self.status_queue = status_queue
                self.session_store = session_store

            def process_command(self, json_command, request_context=None):
                return True

        core_module.LLM = FastTimeoutLLM
        core_module.Interpreter = NoopInterpreter

        core_instance = None
        try:
            core_instance = core_module.Core()
            start = perf_counter()
            core_instance.execute_user_request('测试超时调研')
            elapsed = perf_counter() - start

            assert_true(
                elapsed < 25.0,
                '该测试证明：出现 "Request timed out" 文案时，失败可能早于 25 秒（并非一定等待完整 timeout）。',
            )
        finally:
            if core_instance is not None:
                try:
                    core_instance.cleanup()
                except Exception:
                    pass
            core_module.LLM = original_llm
            core_module.Interpreter = original_interpreter
            if original_home is None:
                os.environ.pop('HOME', None)
            else:
                os.environ['HOME'] = original_home


def main() -> int:
    verify_settings_sqlite_persistence()
    verify_model_applies_runtime_timeout()
    verify_timeout_error_may_happen_before_full_timeout_window()
    print('verify_request_timeout_diagnosis: PASS')
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
    except Exception as exc:
        print(f'verify_request_timeout_diagnosis: FAIL: {exc}')
        exit_code = 1
    raise SystemExit(exit_code)
