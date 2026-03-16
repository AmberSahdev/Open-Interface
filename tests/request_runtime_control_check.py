import base64
import io
import os
import sys
import tempfile
import time
import types
from pathlib import Path

from PIL import Image


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / 'app'

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def install_pyautogui_stub_if_needed() -> None:
    if 'pyautogui' in sys.modules:
        return

    module = types.ModuleType('pyautogui')
    setattr(module, 'PAUSE', 0)
    setattr(module, 'FAILSAFE', False)

    def _noop(*args, **kwargs):
        return None

    setattr(module, 'size', lambda: (1920, 1080))
    setattr(module, 'position', lambda: (0, 0))
    setattr(module, 'screenshot', lambda *args, **kwargs: Image.new('RGB', (1920, 1080), color='white'))

    for attribute_name in (
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


install_pyautogui_stub_if_needed()


from core import Core
from utils.i18n import t
from utils.screen import Screen


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def drain_queue(queue) -> list[dict]:
    events = []
    deadline = time.time() + 0.2
    while queue.empty() and time.time() < deadline:
        time.sleep(0.01)
    while not queue.empty():
        event = queue.get_nowait()
        if isinstance(event, dict):
            events.append(event)
    return events


def verify_request_status_messages_and_restart() -> None:
    original_home = os.environ.get('HOME')
    import core as core_module

    original_llm = core_module.LLM
    original_interpreter = core_module.Interpreter

    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ['HOME'] = temp_dir
        llm_calls = []
        core_instance = None

        class RecordingLLM:
            def __init__(self, *args, **kwargs):
                self.model_name = 'fake-gpt'
                self.settings_dict = {'base_url': 'https://example.invalid/v1/'}

            def get_instructions_for_objective(
                self,
                original_user_request: str,
                step_num: int = 0,
                request_context=None,
            ):
                llm_calls.append((original_user_request, step_num))
                return {
                    'steps': [],
                    'done': 'ok',
                }

            def cleanup(self):
                return None

        class NoopInterpreter:
            def __init__(self, status_queue, session_store=None):
                self.status_queue = status_queue
                self.session_store = session_store

            def process_command(self, json_command, request_context=None):
                return True

        core_module.LLM = RecordingLLM
        core_module.Interpreter = NoopInterpreter

        try:
            core_instance = Core()
            core_instance.execute_user_request('打开虎牙直播')

            events = drain_queue(core_instance.status_queue)
            runtime_messages = [event.get('message', '') for event in events if event.get('type') == 'runtime_status']

            assert_true(
                t('core.requesting_model_initial') in runtime_messages,
                '首次请求时应先推送“正在采集屏幕并请求模型”状态。',
            )
            assert_true(
                any(call == ('打开虎牙直播', 0) for call in llm_calls),
                'execute_user_request() 应触发一次 LLM 调用。',
            )

            llm_calls.clear()
            restarted_request = core_instance.restart_last_request()
            assert_true(restarted_request == '打开虎牙直播', '重试按钮应复用当前会话上一条用户请求。')
            assert_true(
                any(
                    step_num == 0 and '打开虎牙直播' in original_user_request
                    for original_user_request, step_num in llm_calls
                ),
                'restart_last_request() 应重新触发上一条用户请求。',
            )

            core_instance.stop_previous_request(announce=True)
            interrupt_events = drain_queue(core_instance.status_queue)
            interrupt_messages = [event.get('message', '') for event in interrupt_events if event.get('type') == 'runtime_status']
            assert_true(
                t('core.interrupt_requested') in interrupt_messages,
                '显式中断时应推送“已请求中断”状态。',
            )
        finally:
            try:
                if core_instance is not None:
                    core_instance.cleanup()
            except Exception:
                pass
            core_module.LLM = original_llm
            core_module.Interpreter = original_interpreter
            if original_home is None:
                os.environ.pop('HOME', None)
            else:
                os.environ['HOME'] = original_home


def verify_interrupt_discards_model_output() -> None:
    original_home = os.environ.get('HOME')
    import core as core_module

    original_llm = core_module.LLM
    original_interpreter = core_module.Interpreter

    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ['HOME'] = temp_dir
        core_instance = None

        class InterruptingLLM:
            def __init__(self, *args, **kwargs):
                self.model_name = 'fake-gpt'
                self.settings_dict = {'base_url': 'https://example.invalid/v1/'}

            def get_instructions_for_objective(
                self,
                original_user_request: str,
                step_num: int = 0,
                request_context=None,
            ):
                assert core_instance is not None
                core_instance.stop_previous_request()
                return {
                    'steps': [
                        {
                            'function': 'noop',
                            'parameters': {},
                            'human_readable_justification': '这条结果应该被作废。',
                        }
                    ],
                    'done': '这条完成消息不应写入数据库。',
                }

            def cleanup(self):
                return None

        class RecordingInterpreter:
            def __init__(self, status_queue, session_store=None):
                self.status_queue = status_queue
                self.session_store = session_store
                self.call_count = 0

            def process_command(self, json_command, request_context=None):
                self.call_count += 1
                return True

        core_module.LLM = InterruptingLLM
        core_module.Interpreter = RecordingInterpreter

        try:
            core_instance = Core()
            result = core_instance.execute_user_request('启动虎牙直播')
            assert_true(result is None, 'execute_user_request() 顶层调用应通过状态消息结束。')

            messages = core_instance.session_store.list_messages(core_instance.get_active_session_id())
            message_roles_and_content = [(message['role'], message['content']) for message in messages]

            assert_true(
                ('assistant', '这条完成消息不应写入数据库。') not in message_roles_and_content,
                '中断后必须丢弃模型完成输出，不能写 assistant 消息。',
            )
            assert_true(
                ('status', t('core.interrupted')) in message_roles_and_content,
                '中断后应写入一条状态消息“已中断”。',
            )

            interpreter = core_instance.interpreter
            assert_true(interpreter is not None, '测试前置失败：解释器未初始化。')
            assert_true(
                getattr(interpreter, 'call_count', 0) == 0,
                '中断发生在模型返回后时，后续动作不应被执行。',
            )
        finally:
            try:
                if core_instance is not None:
                    core_instance.cleanup()
            except Exception:
                pass
            core_module.LLM = original_llm
            core_module.Interpreter = original_interpreter
            if original_home is None:
                os.environ.pop('HOME', None)
            else:
                os.environ['HOME'] = original_home


def verify_interrupt_blocks_recursive_followup() -> None:
    original_home = os.environ.get('HOME')
    import core as core_module

    original_llm = core_module.LLM
    original_interpreter = core_module.Interpreter

    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ['HOME'] = temp_dir
        core_instance = None
        llm_calls = []

        class RecursiveLLM:
            def __init__(self, *args, **kwargs):
                self.model_name = 'fake-gpt'
                self.settings_dict = {'base_url': 'https://example.invalid/v1/'}

            def get_instructions_for_objective(
                self,
                original_user_request: str,
                step_num: int = 0,
                request_context=None,
            ):
                llm_calls.append(step_num)
                return {
                    'steps': [
                        {
                            'function': 'sleep',
                            'parameters': {'secs': 0},
                            'human_readable_justification': '执行后将触发中断。',
                        }
                    ],
                    'done': None,
                }

            def cleanup(self):
                return None

        class InterruptingInterpreter:
            def __init__(self, status_queue, session_store=None):
                self.status_queue = status_queue
                self.session_store = session_store
                self.call_count = 0

            def process_command(self, json_command, request_context=None):
                self.call_count += 1
                assert core_instance is not None
                core_instance.stop_previous_request()
                return True

        core_module.LLM = RecursiveLLM
        core_module.Interpreter = InterruptingInterpreter

        try:
            core_instance = Core()
            core_instance.execute_user_request('打开虎牙直播并继续操作')

            assert_true(llm_calls == [0], '中断后不应继续发起下一轮递归模型请求。')

            messages = core_instance.session_store.list_messages(core_instance.get_active_session_id())
            status_messages = [message['content'] for message in messages if message['role'] == 'status']
            assert_true(
                t('core.interrupted') in status_messages,
                '递归续跑被拦截后应记录“已中断”。',
            )

            interpreter = core_instance.interpreter
            assert_true(interpreter is not None, '测试前置失败：解释器未初始化。')
            assert_true(
                getattr(interpreter, 'call_count', 0) == 1,
                '中断发生在首个步骤后时，不应再执行后续步骤。',
            )
        finally:
            try:
                if core_instance is not None:
                    core_instance.cleanup()
            except Exception:
                pass
            core_module.LLM = original_llm
            core_module.Interpreter = original_interpreter
            if original_home is None:
                os.environ.pop('HOME', None)
            else:
                os.environ['HOME'] = original_home


def verify_prompt_image_scaling() -> None:
    screen = Screen()
    source_image = Image.new('RGB', (3440, 1440), color='white')

    def fake_get_screenshot():
        return source_image.copy()

    def fake_get_size():
        return 3440, 1440

    original_get_screenshot = screen.get_screenshot
    original_get_size = screen.get_size

    try:
        screen.get_screenshot = fake_get_screenshot
        screen.get_size = fake_get_size
        payload = screen.get_visual_prompt_payload()
    finally:
        screen.get_screenshot = original_get_screenshot
        screen.get_size = original_get_size

    decoded_image = Image.open(io.BytesIO(base64.b64decode(payload['annotated_image_base64'])))

    assert_true(
        decoded_image.width <= screen.MAX_PROMPT_IMAGE_WIDTH,
        '视觉提示图宽度应被压缩到约定上限内。',
    )
    assert_true(
        decoded_image.height <= screen.MAX_PROMPT_IMAGE_HEIGHT,
        '视觉提示图高度应被压缩到约定上限内。',
    )
    assert_true(
        payload['frame_context']['captured_screen'] == {'width': 3440, 'height': 1440},
        '截图压缩后仍应保留原始捕获尺寸供坐标映射使用。',
    )


def main() -> int:
    verify_request_status_messages_and_restart()
    verify_interrupt_discards_model_output()
    verify_interrupt_blocks_recursive_followup()
    verify_prompt_image_scaling()
    print('request_runtime_control_check: success')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f'request_runtime_control_check: failed: {exc}')
        raise SystemExit(1)
