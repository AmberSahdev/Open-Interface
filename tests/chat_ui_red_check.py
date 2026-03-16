import importlib
import queue
import sys
import traceback
from collections import Counter
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / 'app'))


SEEDED_SESSIONS = [
    {
        'id': 'session-1',
        'title': '销售线索跟进',
        'updated_at': '2026-03-11T12:00:00+08:00',
    },
    {
        'id': 'session-2',
        'title': '财务对账处理',
        'updated_at': '2026-03-11T11:30:00+08:00',
    },
]

SEEDED_MESSAGES = [
    {
        'id': 'message-1',
        'role': 'user',
        'content': '请继续刚才的销售跟进流程。',
    },
    {
        'id': 'message-2',
        'role': 'assistant',
        'content': '好的，当前已经打开 CRM 客户详情页。',
    },
]

REQUIRED_ZH_COPY = {
    '会话列表',
    '暂无消息与执行记录',
    '新会话',
    '正在运行',
}


def collect_widget_classes(widget):
    widget_classes = Counter()

    def walk(current_widget):
        widget_classes[current_widget.winfo_class()] += 1
        for child in current_widget.winfo_children():
            walk(child)

    walk(widget)
    return widget_classes


def destroy_widget(widget):
    if widget is None:
        return

    try:
        widget.destroy()
    except Exception:
        pass


def test_normal_path_app_bootstrap_hydrates_existing_sessions_and_messages():
    app_module = importlib.import_module('app')

    original_core = app_module.Core
    original_ui = app_module.UI
    recorded = {
        'list_sessions_calls': 0,
        'list_timeline_calls': [],
        'hydrated_sessions': None,
        'hydrated_messages': None,
    }
    app_instance = None

    class FakeSessionStore:
        def list_sessions(self):
            recorded['list_sessions_calls'] += 1
            return SEEDED_SESSIONS

        def list_timeline_entries(self, session_id):
            recorded['list_timeline_calls'].append(session_id)
            return SEEDED_MESSAGES

    class FakeCore:
        def __init__(self):
            self.status_queue = queue.Queue()
            self.session_store = FakeSessionStore()
            self.active_session_id = 'session-1'

        def execute_user_request(self, user_request):
            return user_request

        def get_startup_issue(self):
            return None

        def build_session_view_issue(self, error):
            return {'message': str(error)}

    class FakeMainWindow:
        def __init__(self):
            self.user_request_queue = queue.Queue()

        def load_session_list(self, sessions):
            recorded['hydrated_sessions'] = sessions

        def load_message_history(self, messages):
            recorded['hydrated_messages'] = messages

        def load_timeline_history(self, messages):
            recorded['hydrated_messages'] = messages

        def destroy(self):
            return None

    class FakeUI:
        def __init__(self):
            self.main_window = FakeMainWindow()

        def hydrate_session_view(self, active_session_id, sessions, timeline_entries, runtime_status=''):
            recorded['hydrated_sessions'] = sessions
            recorded['hydrated_messages'] = timeline_entries

        def load_session_list(self, sessions):
            recorded['hydrated_sessions'] = sessions

        def load_message_history(self, messages):
            recorded['hydrated_messages'] = messages

        def load_timeline_history(self, messages):
            recorded['hydrated_messages'] = messages

        def display_current_status(self, text):
            return text

        def run(self):
            return None

    setattr(app_module, 'Core', FakeCore)
    setattr(app_module, 'UI', FakeUI)

    try:
        app_instance = app_module.App()
    finally:
        if app_instance is not None and hasattr(app_instance, 'cleanup'):
            try:
                app_instance.cleanup()
            except Exception:
                pass
        setattr(app_module, 'Core', original_core)
        setattr(app_module, 'UI', original_ui)

    errors = []
    if recorded['list_sessions_calls'] != 1:
        errors.append(
            'App 启动阶段应调用 1 次 session_store.list_sessions() 注水左侧会话列表；'
            f'当前调用次数={recorded["list_sessions_calls"]}'
        )
    if recorded['list_timeline_calls'] != ['session-1']:
        errors.append(
            'App 启动阶段应按 active_session_id 调用 session_store.list_timeline_entries() 注水右侧详情；'
            f'当前调用序列={recorded["list_timeline_calls"]}'
        )
    if recorded['hydrated_sessions'] != SEEDED_SESSIONS:
        errors.append(
            'App 启动后应把已有会话快照交给 UI 渲染；'
            f'当前注水会话={recorded["hydrated_sessions"]!r}'
        )
    if recorded['hydrated_messages'] != SEEDED_MESSAGES:
        errors.append(
            'App 启动后应把当前会话消息历史交给 UI 渲染；'
            f'当前注水消息={recorded["hydrated_messages"]!r}'
        )

    assert not errors, '\n'.join(errors)


def test_boundary_main_window_is_large_enough_for_chat_layout():
    ui_module = importlib.import_module('ui')
    ui_instance = ui_module.UI()

    try:
        main_window = ui_instance.main_window
        main_window.update_idletasks()

        width = main_window.winfo_width()
        height = main_window.winfo_height()
        min_width, min_height = main_window.minsize()
        widget_classes = collect_widget_classes(main_window)
        scroll_capable_count = sum(
            widget_classes.get(widget_name, 0)
            for widget_name in ('Canvas', 'Text', 'Listbox', 'Treeview')
        )

        errors = []
        if width < 1180 or height < 760:
            errors.append(
                '主窗口默认尺寸应至少达到 1180x760，才能承载左侧会话列表与右侧详情区；'
                f'当前尺寸={width}x{height}'
            )
        if min_width < 980 or min_height < 640:
            errors.append(
                '主窗口最小尺寸应至少达到 980x640，避免缩放后主区域被挤压；'
                f'当前 minsize={min_width}x{min_height}'
            )
        if widget_classes.get('Text', 0) < 1:
            errors.append(
                '聊天输入区应升级为多行 Text 组件，而不是继续停留在单行输入框。'
            )
        if scroll_capable_count < 2:
            errors.append(
                '双栏聊天界面至少需要两个可滚动/可承载长内容的区域（如会话列表与消息历史）；'
                f'当前可滚动候选组件统计={dict(widget_classes)}'
            )

        assert not errors, '\n'.join(errors)
    finally:
        destroy_widget(ui_instance.main_window)


def test_negative_ui_separates_runtime_status_from_history_and_registers_i18n_copy():
    ui_module = importlib.import_module('ui')
    main_window_class = ui_module.UI.MainWindow

    missing_methods = []
    for method_name in ('load_session_list', 'load_message_history', 'set_runtime_status'):
        if not callable(getattr(ui_module.UI, method_name, None)) and not callable(
            getattr(main_window_class, method_name, None)
        ):
            missing_methods.append(method_name)

    i18n_module = importlib.import_module('utils.i18n')
    zh_values = set(i18n_module.TRANSLATIONS.get('zh-CN', {}).values())
    missing_copy = sorted(REQUIRED_ZH_COPY - zh_values)

    errors = []
    if missing_methods:
        errors.append(
            '为避免运行状态与历史消息混杂，UI 需要提供独立渲染入口；'
            f'当前缺少方法={missing_methods}'
        )
    if missing_copy:
        errors.append(
            '新聊天界面文案应先进入 app/utils/i18n.py，再由 UI 引用；'
            f'当前缺少中文文案={missing_copy}'
        )

    assert not errors, '\n'.join(errors)


TEST_CASES = [
    (
        'normal_path_app_bootstrap_hydrates_existing_sessions_and_messages',
        test_normal_path_app_bootstrap_hydrates_existing_sessions_and_messages,
    ),
    (
        'boundary_main_window_is_large_enough_for_chat_layout',
        test_boundary_main_window_is_large_enough_for_chat_layout,
    ),
    (
        'negative_ui_separates_runtime_status_from_history_and_registers_i18n_copy',
        test_negative_ui_separates_runtime_status_from_history_and_registers_i18n_copy,
    ),
]


def main():
    red_failures = 0
    unexpected_passes = 0

    for test_name, test_func in TEST_CASES:
        print(f'=== RUN {test_name}')
        try:
            test_func()
        except Exception:
            red_failures += 1
            print(f'--- FAIL {test_name}')
            traceback.print_exc()
        else:
            unexpected_passes += 1
            print(f'--- UNEXPECTED PASS {test_name}')
            print('该红灯用例未失败，需要在 Green 前补强断言。')

    print('=== RED SUMMARY ===')
    print(f'red_failures={red_failures}')
    print(f'unexpected_passes={unexpected_passes}')

    if unexpected_passes:
        return 2

    if red_failures:
        return 1

    print('未捕获到任何红灯失败，这与当前子任务预期不符。')
    return 3


if __name__ == '__main__':
    sys.exit(main())
