import os
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP_DIR = os.path.join(ROOT_DIR, 'app')

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from agent_memory import create_agent_memory
import core as core_module
from core import Core


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get_instructions_for_objective(self, prompt, step_num, request_context=None):
        self.calls.append({
            'prompt': prompt,
            'step_num': step_num,
        })
        index = min(step_num, len(self.responses) - 1)
        response = self.responses[index]
        return {
            'steps': list(response.get('steps') or []),
            'done': response.get('done'),
        }


class FakeInterpreter:
    def __init__(self, process_results, after_process=None):
        self.process_results = list(process_results)
        self.after_process = after_process
        self.commands = []
        self.last_execution_snapshot = {
            'function_name': 'click',
            'parameters': {'x': 10, 'y': 20},
            'coordinate_resolution': None,
        }

    def process_command(self, step, request_context):
        self.commands.append(dict(step))
        result = self.process_results.pop(0)
        if callable(self.after_process):
            self.after_process(step, request_context)
        return result

    def get_last_execution_snapshot(self):
        return dict(self.last_execution_snapshot)


def build_core(disable_local_step_verification, llm, interpreter):
    core = Core.__new__(Core)
    core.llm = llm
    core.interpreter = interpreter
    core.step_verifier = object()
    core.settings_dict = {
        'runtime': {
            'play_ding_on_completion': False,
            'disable_local_step_verification': disable_local_step_verification,
        },
    }
    core.startup_issue = None
    core.session_store = None
    core.active_session_id = 'session-1'
    core.request_sequence = 0
    core.active_request_token = 7
    core.cancelled_request_tokens = set()
    core.interrupt_execution = False

    core.runtime_statuses = []
    core.status_messages = []
    core.assistant_messages = []
    core.finalized_requests = []
    core.capture_calls = []
    core.verify_calls = []

    def emit_runtime_status(message='', session_id=None, issue=None):
        core.runtime_statuses.append({
            'message': message,
            'session_id': session_id,
            'issue': issue,
        })

    def store_status_message(request_context, message, issue=None):
        core.status_messages.append({
            'message': message,
            'issue': issue,
        })

    def store_assistant_message(request_context, message):
        core.assistant_messages.append(message)

    def finalize_request(request_context):
        core.finalized_requests.append(request_context.get('request_id'))
        request_context['request_finalized'] = True

    def attach_frame_context(request_context, instructions):
        return None

    def capture_before_step(step):
        core.capture_calls.append(dict(step))
        return 'before-image'

    def verify_step(step, active_interpreter, before_image):
        core.verify_calls.append({
            'step': dict(step),
            'before_image': before_image,
        })
        return {
            'status': 'passed',
            'reason': 'screen_changed',
            'function': str(step.get('function') or ''),
            'expected_outcome': str(step.get('expected_outcome') or ''),
            'global_change_ratio': 0.1,
            'local_change_ratio': 0.1,
        }

    core._emit_runtime_status = emit_runtime_status
    core._store_status_message = store_status_message
    core._store_assistant_message = store_assistant_message
    core._finalize_request = finalize_request
    core._attach_frame_context = attach_frame_context
    core._capture_before_step = capture_before_step
    core._verify_step = verify_step
    core.play_ding_on_completion = lambda: None

    return core


def build_request_context():
    return {
        'prompt': 'test prompt',
        'request_id': 'request-1',
        'request_token': 7,
        'session_id': 'session-1',
        'user_request': 'do something',
        'user_message_id': 1,
        'interrupted_recorded': False,
        'request_finalized': False,
        'next_step_index': 1,
        'agent_memory': create_agent_memory(),
    }


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_default_mode_runs_verification():
    step = {
        'function': 'click',
        'parameters': {'x': 10, 'y': 20},
        'human_readable_justification': 'click once',
    }
    llm = FakeLLM([
        {'steps': [step], 'done': None},
        {'steps': [], 'done': '任务完成'},
    ])
    interpreter = FakeInterpreter([True])
    core = build_core(False, llm, interpreter)
    request_context = build_request_context()

    result = core.execute(request_context['prompt'], request_context=request_context)

    assert_true(result == '任务完成', '默认模式应返回完成结果。')
    assert_true(len(core.capture_calls) == 1, '默认模式应截图一次用于验证。')
    assert_true(len(core.verify_calls) == 1, '默认模式应调用本地验证。')
    assert_true(len(interpreter.commands) == 1, '默认模式仍应只执行一个 step。')
    assert_true(len(llm.calls) == 2, '默认模式在未 done 时应继续下一轮。')
    recent_actions = request_context['agent_memory']['recent_actions']
    assert_true(recent_actions[0]['verification_status'] == 'passed', '默认模式应记录真实验证结果。')


def test_disabled_mode_skips_verification_and_sleeps_once():
    step = {
        'function': 'click',
        'parameters': {'x': 10, 'y': 20},
        'human_readable_justification': 'click once',
    }
    llm = FakeLLM([
        {'steps': [step], 'done': None},
        {'steps': [], 'done': '任务完成'},
    ])
    interpreter = FakeInterpreter([True])
    core = build_core(True, llm, interpreter)
    request_context = build_request_context()

    sleep_calls = []
    original_sleep = core_module.time.sleep
    core_module.time.sleep = lambda seconds: sleep_calls.append(seconds)
    try:
        result = core.execute(request_context['prompt'], request_context=request_context)
    finally:
        core_module.time.sleep = original_sleep

    assert_true(result == '任务完成', '关闭本地验证时仍应完成请求。')
    assert_true(len(core.capture_calls) == 0, '关闭本地验证时不应采集本地验证截图。')
    assert_true(len(core.verify_calls) == 0, '关闭本地验证时不应调用本地验证器。')
    assert_true(sleep_calls == [1.0], '关闭本地验证时应固定等待 1 秒。')
    assert_true(len(interpreter.commands) == 1, '关闭本地验证时仍应只执行一个 step。')
    assert_true(len(llm.calls) == 2, '关闭本地验证时未 done 也应进入下一轮。')
    recent_actions = request_context['agent_memory']['recent_actions']
    assert_true(recent_actions[0]['verification_status'] == 'skipped', '关闭本地验证时应记录跳过状态。')


def test_execution_failure_still_stops():
    step = {
        'function': 'click',
        'parameters': {'x': 10, 'y': 20},
    }
    llm = FakeLLM([
        {'steps': [step], 'done': None},
    ])
    interpreter = FakeInterpreter([False])
    core = build_core(True, llm, interpreter)
    request_context = build_request_context()

    result = core.execute(request_context['prompt'], request_context=request_context)

    assert_true(result == '无法执行该请求', '执行失败时应沿用现有失败返回。')
    assert_true(len(core.verify_calls) == 0, '执行失败后不应进入验证。')
    recent_failures = request_context['agent_memory']['recent_failures']
    assert_true(recent_failures[0]['reason'] == 'execution_failed', '执行失败时应记录 execution_failed。')
    assert_true(len(llm.calls) == 1, '执行失败时不应继续下一轮。')


def test_interrupt_still_prevents_next_loop():
    step = {
        'function': 'click',
        'parameters': {'x': 10, 'y': 20},
    }

    llm = FakeLLM([
        {'steps': [step], 'done': None},
        {'steps': [], 'done': '不应到达这里'},
    ])
    interpreter = FakeInterpreter([True])
    core = build_core(True, llm, interpreter)
    request_context = build_request_context()

    def cancel_request(step_payload, request_payload):
        core.cancelled_request_tokens.add(int(request_payload['request_token']))

    interpreter.after_process = cancel_request
    result = core.execute(request_context['prompt'], request_context=request_context)

    assert_true(result == '已中断', '中断后应立即停止，不进入下一轮。')
    assert_true(len(llm.calls) == 1, '中断后不应继续请求下一轮模型结果。')
    assert_true(len(core.assistant_messages) == 0, '中断后迟到结果不应落地为 assistant 消息。')


def main():
    test_default_mode_runs_verification()
    test_disabled_mode_skips_verification_and_sleeps_once()
    test_execution_failure_still_stops()
    test_interrupt_still_prevents_next_loop()
    print('verify_disable_local_step_verification.py: all checks passed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'verify_disable_local_step_verification.py: failed - {exc}')
        sys.exit(1)
