import importlib
import inspect
import os
import sys
import tempfile
import traceback
import types
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / 'app'))


HISTORY_USER = '历史用户消息：请先打开 CRM 并找到客户小王的工单。'
HISTORY_ASSISTANT = '历史助手消息：已经打开 CRM，当前停留在客户详情页。'
CURRENT_REQUEST = '请继续刚才的流程，并补充导出最新处理记录。'

RESET_METHOD_NAMES = {
    'begin_request',
    'prepare_for_request',
    'reset_for_new_request',
    'reset_runtime_state',
    'reset_state',
    'start_new_request',
}

REQUEST_BOUNDARY_PARAM_NAMES = {
    'is_new_request',
    'new_request',
    'request_context',
    'top_level_request',
}


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
    setattr(module, 'screenshot', _noop)

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


def seed_session_history(temp_dir: str) -> Path:
    session_store_module = importlib.import_module('session_store')
    session_store_class = session_store_module.SessionStore

    db_path = Path(temp_dir) / '.open-interface' / 'session_history.db'
    store = session_store_class(db_path)
    store.initialize()

    session = store.create_session('P0-3 红灯验证会话')
    store.create_message(session['id'], 'user', HISTORY_USER)
    store.create_message(session['id'], 'assistant', HISTORY_ASSISTANT)

    return db_path


def build_core_with_recording_llm(temp_dir: str, recursive: bool):
    install_pyautogui_stub_if_needed()
    core_module = importlib.import_module('core')

    original_home = os.environ.get('HOME')
    original_llm = core_module.LLM
    original_interpreter = core_module.Interpreter
    recorded_calls = []

    os.environ['HOME'] = temp_dir

    class RecordingLLM:
        def __init__(self, *args, **kwargs):
            self.call_index = 0

        def get_instructions_for_objective(
            self,
            original_user_request: str,
            step_num: int = 0,
            request_context=None,
        ):
            session_history_snapshot = []
            request_origin = None
            if isinstance(request_context, dict):
                raw_snapshot = request_context.get('session_history_snapshot')
                if isinstance(raw_snapshot, list):
                    session_history_snapshot = [dict(item) for item in raw_snapshot if isinstance(item, dict)]
                request_origin = request_context.get('request_origin')

            recorded_calls.append(
                {
                    'original_user_request': original_user_request,
                    'step_num': step_num,
                    'session_history_snapshot': session_history_snapshot,
                    'request_origin': request_origin,
                }
            )

            if recursive and self.call_index == 0:
                self.call_index += 1
                return {
                    'steps': [
                        {
                            'function': 'sleep',
                            'parameters': {'secs': 0},
                            'human_readable_justification': '触发递归阶段以验证上下文复用。',
                        }
                    ],
                    'done': None,
                }

            self.call_index += 1
            return {
                'steps': [],
                'done': 'red-stop',
            }

        def cleanup(self):
            return None

    class NoopInterpreter:
        def __init__(self, status_queue, session_store=None):
            self.status_queue = status_queue
            self.session_store = session_store

        def process_command(self, json_command, request_context=None):
            return True

        def process_commands(self, json_commands, request_context=None):
            return True

        def get_last_execution_snapshot(self):
            return {
                'function_name': 'sleep',
                'parameters': {'secs': 0},
                'coordinate_resolution': None,
            }

    setattr(core_module, 'LLM', RecordingLLM)
    setattr(core_module, 'Interpreter', NoopInterpreter)

    core_instance = core_module.Core()

    def cleanup():
        try:
            if hasattr(core_instance, 'cleanup'):
                core_instance.cleanup()
        finally:
            setattr(core_module, 'LLM', original_llm)
            setattr(core_module, 'Interpreter', original_interpreter)
            if original_home is None:
                os.environ.pop('HOME', None)
            else:
                os.environ['HOME'] = original_home

    return core_instance, recorded_calls, cleanup


def test_normal_path_followup_request_injects_sqlite_history():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = seed_session_history(temp_dir)
        core_instance, recorded_calls, cleanup = build_core_with_recording_llm(
            temp_dir=temp_dir,
            recursive=False,
        )

        try:
            core_instance.execute_user_request(CURRENT_REQUEST)
        finally:
            cleanup()

        assert db_path.exists(), '红灯前置条件失败：测试数据库未成功创建。'
        assert recorded_calls, 'Core.execute_user_request() 应至少触发 1 次 LLM 调用。'

        first_prompt = recorded_calls[0]['original_user_request']
        first_snapshot = recorded_calls[0]['session_history_snapshot']

        assert first_prompt == CURRENT_REQUEST, (
            '统一 Prompt Builder 重构后，LLM 顶层目标应保持为原始用户请求，'
            f'当前观察到: {first_prompt!r}'
        )
        snapshot_text = ' '.join(str(item.get('content') or '') for item in first_snapshot)
        assert HISTORY_USER in snapshot_text and HISTORY_ASSISTANT in snapshot_text, (
            '同一会话第二次请求时，历史消息应进入结构化 session_history_snapshot，而不是拼进原始请求；'
            f'current_snapshot={first_snapshot!r}'
        )
        assert recorded_calls[0]['request_origin'] == 'new_request', '首次请求应标记为 new_request。'


def test_boundary_recursive_step_reuses_single_history_snapshot():
    with tempfile.TemporaryDirectory() as temp_dir:
        seed_session_history(temp_dir)
        core_instance, recorded_calls, cleanup = build_core_with_recording_llm(
            temp_dir=temp_dir,
            recursive=True,
        )

        try:
            core_instance.execute_user_request(CURRENT_REQUEST)
        finally:
            cleanup()

        assert len(recorded_calls) >= 2, (
            '该边界用例需要至少 2 次 LLM 调用，以覆盖 step_num=0 与 step_num=1。'
        )

        first_call = recorded_calls[0]
        second_call = recorded_calls[1]
        assert [first_call['step_num'], second_call['step_num']] == [0, 1], (
            '递归阶段应按 step_num=0 -> step_num=1 演进；'
            f'当前调用序列为: {[call["step_num"] for call in recorded_calls[:2]]}'
        )

        second_snapshot = second_call['session_history_snapshot']
        first_snapshot = first_call['session_history_snapshot']
        first_snapshot_text = ' '.join(str(item.get('content') or '') for item in first_snapshot)
        second_snapshot_text = ' '.join(str(item.get('content') or '') for item in second_snapshot)

        assert first_snapshot == second_snapshot, (
            'step_num>0 的递归阶段应复用同一份结构化历史快照，不能丢失，也不能重复生成；'
            f'first_snapshot={first_snapshot!r}, second_snapshot={second_snapshot!r}'
        )
        assert first_snapshot_text.count(HISTORY_USER) == 1, (
            '递归阶段应保留且只保留一份用户历史快照；'
            f'second_snapshot={second_snapshot!r}'
        )
        assert second_snapshot_text.count(HISTORY_ASSISTANT) == 1, (
            '递归阶段仍应保留裁剪后的助手历史快照；'
            f'second_snapshot={second_snapshot!r}'
        )


def test_negative_stateful_gpt4o_exposes_request_reset_boundary():
    install_pyautogui_stub_if_needed()
    gpt4o_module = importlib.import_module('models.gpt4o')

    if not hasattr(gpt4o_module, 'GPT4o'):
        raise AssertionError('缺少 models.gpt4o.GPT4o，无法验证 stateful 适配器重置策略。')

    gpt4o_class = gpt4o_module.GPT4o
    public_methods = {
        name
        for name, member in inspect.getmembers(gpt4o_class, inspect.isfunction)
        if not name.startswith('__')
    }

    signature = inspect.signature(gpt4o_class.get_instructions_for_objective)
    has_reset_method = bool(RESET_METHOD_NAMES & public_methods)
    has_request_boundary_param = any(
        name in signature.parameters for name in REQUEST_BOUNDARY_PARAM_NAMES
    )

    assert has_reset_method or has_request_boundary_param, (
        'gpt4o 作为 stateful 适配器，需要在新顶层请求开始时暴露显式重置能力或请求边界信号，'
        '否则无法消除跨请求运行态污染风险；'
        f'public_methods={sorted(public_methods)}, signature={signature}'
    )


TEST_CASES = [
    (
        'normal_path_followup_request_injects_sqlite_history',
        test_normal_path_followup_request_injects_sqlite_history,
    ),
    (
        'boundary_recursive_step_reuses_single_history_snapshot',
        test_boundary_recursive_step_reuses_single_history_snapshot,
    ),
    (
        'negative_stateful_gpt4o_exposes_request_reset_boundary',
        test_negative_stateful_gpt4o_exposes_request_reset_boundary,
    ),
]


def main():
    passed = 0
    failed = 0

    for test_name, test_func in TEST_CASES:
        print(f'=== RUN {test_name}')
        try:
            test_func()
        except Exception:
            failed += 1
            print(f'--- FAIL {test_name}')
            traceback.print_exc()
        else:
            passed += 1
            print(f'--- PASS {test_name}')

    print('=== REGRESSION SUMMARY ===')
    print(f'passed={passed}')
    print(f'failed={failed}')
    print(f'total={len(TEST_CASES)}')

    if failed:
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
