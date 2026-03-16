import importlib
import os
import queue
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / 'app'))


def destroy_widget(widget: Any) -> None:
    if widget is None:
        return

    try:
        widget.destroy()
    except Exception:
        pass


def test_session_store_regression_suite() -> None:
    session_store_module = importlib.import_module('tests.session_store_red_check')
    session_store_module.test_normal_path_store_can_persist_session_message_and_log()
    session_store_module.test_boundary_initialize_new_database_is_idempotent_and_creates_schema()
    session_store_module.test_negative_core_initializes_schema_before_llm_failure()


def test_session_context_regression_suite() -> None:
    session_context_module = importlib.import_module('tests.session_context_red_check')
    session_context_module.test_normal_path_followup_request_injects_sqlite_history()
    session_context_module.test_boundary_recursive_step_reuses_single_history_snapshot()
    session_context_module.test_negative_stateful_gpt4o_exposes_request_reset_boundary()


def test_chat_ui_regression_suite() -> None:
    chat_ui_module = importlib.import_module('tests.chat_ui_red_check')
    chat_ui_module.test_normal_path_app_bootstrap_hydrates_existing_sessions_and_messages()
    chat_ui_module.test_boundary_main_window_is_large_enough_for_chat_layout()
    chat_ui_module.test_negative_ui_separates_runtime_status_from_history_and_registers_i18n_copy()


def test_session_switch_restore_and_timeline_regression() -> None:
    core_module = importlib.import_module('core')

    original_home = os.environ.get('HOME')
    original_llm = core_module.LLM
    original_interpreter = core_module.Interpreter

    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ['HOME'] = temp_dir

        class StubLLM:
            def __init__(self, *args, **kwargs):
                return None

            def cleanup(self) -> None:
                return None

        class StubInterpreter:
            def __init__(self, status_queue, session_store=None):
                self.status_queue = status_queue
                self.session_store = session_store

        setattr(core_module, 'LLM', StubLLM)
        setattr(core_module, 'Interpreter', StubInterpreter)

        primary_core = None
        restored_core = None

        try:
            primary_core = core_module.Core()
            store = primary_core.session_store
            assert store is not None, 'Core 启动后应持有可用的 SessionStore。'

            first_session_id = primary_core.get_active_session_id()
            second_session = store.create_session('恢复校验会话')
            store.touch_session(second_session['id'], updated_at='2099-01-01T00:00:00+00:00')
            store.set_last_active_session_id(first_session_id)

            message = store.create_message(first_session_id, 'user', '请保留这条时间线消息。')
            store.append_execution_log(
                session_id=first_session_id,
                message_id=message['id'],
                step_index=1,
                status='succeeded',
                justification='已完成恢复与时间线校验。',
                function_name='noop',
                parameters_json='{}',
            )

            timeline_entries = store.list_timeline_entries(first_session_id)
            assert len(timeline_entries) == 2, '统一时间线应同时返回消息与执行记录。'
            assert timeline_entries[0]['timeline_type'] == 'message', '时间线首条应为消息记录。'
            assert timeline_entries[1]['timeline_type'] == 'execution_log', '时间线应包含执行记录条目。'

            switched = primary_core.switch_active_session(second_session['id'])
            assert switched is True, '切换到其他会话时应返回 True。'
            assert primary_core.get_active_session_id() == second_session['id'], '切换后 active_session_id 应更新。'
            assert primary_core.switch_active_session(second_session['id']) is False, '重复切换当前会话应保持幂等。'
            assert primary_core.switch_active_session(first_session_id) is True, '切回原会话时应成功更新 active_session_id。'

            primary_core.cleanup()
            primary_core = None

            restored_core = core_module.Core()
            assert restored_core.get_active_session_id() == first_session_id, (
                '应用重启后应优先恢复 last_active_session_id，而不是仅按最近更新时间恢复。'
            )
        finally:
            if primary_core is not None:
                try:
                    primary_core.cleanup()
                except Exception:
                    pass
            if restored_core is not None:
                try:
                    restored_core.cleanup()
                except Exception:
                    pass

            setattr(core_module, 'LLM', original_llm)
            setattr(core_module, 'Interpreter', original_interpreter)

            if original_home is None:
                os.environ.pop('HOME', None)
            else:
                os.environ['HOME'] = original_home


def test_app_event_filter_and_new_session_regression() -> None:
    app_module = importlib.import_module('app')

    original_core = app_module.Core
    original_ui = app_module.UI
    app_instance = None
    recorded: dict[str, Any] = {
        'hydrate_calls': [],
        'session_list_calls': [],
        'timeline_requests': [],
        'appended_messages': [],
        'appended_logs': [],
        'runtime_statuses': [],
    }

    class FakeSessionStore:
        def __init__(self):
            self.sessions = [
                {
                    'id': 'session-1',
                    'title': '主会话',
                    'updated_at': '2026-03-11T17:00:00+08:00',
                },
                {
                    'id': 'session-2',
                    'title': '次会话',
                    'updated_at': '2026-03-11T16:30:00+08:00',
                },
            ]
            self.timeline_entries = {
                'session-1': [
                    {
                        'id': 'message-1',
                        'timeline_type': 'message',
                        'role': 'user',
                        'content': '请回到主会话。',
                        'created_at': '2026-03-11T17:00:00+08:00',
                    }
                ],
                'session-2': [
                    {
                        'id': 'message-2',
                        'timeline_type': 'message',
                        'role': 'assistant',
                        'content': '这里是第二个会话。',
                        'created_at': '2026-03-11T16:30:00+08:00',
                    }
                ],
                'session-3': [],
            }

        def list_sessions(self):
            recorded['session_list_calls'].append('list_sessions')
            return list(self.sessions)

        def list_timeline_entries(self, session_id):
            recorded['timeline_requests'].append(session_id)
            return list(self.timeline_entries.get(session_id, []))

    class FakeCore:
        def __init__(self):
            self.status_queue = queue.Queue()
            self.session_store = FakeSessionStore()
            self.active_session_id = 'session-1'

        def get_startup_issue(self):
            return None

        def get_active_session_id(self):
            return self.active_session_id

        def switch_active_session(self, session_id):
            if session_id == self.active_session_id:
                return False
            self.active_session_id = session_id
            return True

        def create_session_and_activate(self):
            session = {
                'id': 'session-3',
                'title': '新会话',
                'updated_at': '2026-03-11T17:05:00+08:00',
            }
            self.session_store.sessions.insert(0, session)
            self.active_session_id = session['id']
            return session

        def build_session_view_issue(self, error):
            return {'message': str(error)}

        def cleanup(self):
            return None

    class FakeMainWindow:
        def __init__(self):
            self.user_request_queue = queue.Queue()
            self.active_session_id = None

    class FakeUI:
        def __init__(self):
            self.main_window = FakeMainWindow()

        def hydrate_session_view(self, active_session_id, sessions, timeline_entries, runtime_status=''):
            recorded['hydrate_calls'].append({
                'active_session_id': active_session_id,
                'sessions': list(sessions),
                'timeline_entries': list(timeline_entries),
                'runtime_status': runtime_status,
            })

        def load_session_list(self, sessions):
            recorded['session_list_calls'].append(list(sessions))

        def append_message_item(self, message):
            recorded['appended_messages'].append(dict(message))

        def append_execution_log_item(self, execution_log):
            recorded['appended_logs'].append(dict(execution_log))

        def set_runtime_status(self, status):
            recorded['runtime_statuses'].append(status)

        def display_current_status(self, text):
            recorded['runtime_statuses'].append(text)

        def run(self):
            return None

    setattr(app_module, 'Core', FakeCore)
    setattr(app_module, 'UI', FakeUI)

    try:
        app_instance = app_module.App()

        assert recorded['hydrate_calls'], 'App 启动时应执行首屏会话注水。'
        first_hydration = recorded['hydrate_calls'][0]
        assert first_hydration['active_session_id'] == 'session-1', '首屏应注水当前 active_session_id。'
        assert len(first_hydration['timeline_entries']) == 1, '首屏应加载当前会话的时间线。'

        app_instance.handle_core_event({
            'type': 'message_persisted',
            'session_id': 'session-2',
            'message': {
                'id': 'ignored-message',
                'role': 'assistant',
                'content': '这条消息不应污染当前详情区。',
            },
        })
        assert recorded['appended_messages'] == [], '非当前会话消息不应追加到当前详情区。'

        app_instance.handle_core_event({
            'type': 'execution_log_persisted',
            'session_id': 'session-2',
            'execution_log': {
                'id': 'ignored-log',
                'step_index': 1,
                'status': 'succeeded',
            },
        })
        assert recorded['appended_logs'] == [], '非当前会话执行记录不应追加到当前详情区。'

        app_instance.handle_core_event({
            'type': 'message_persisted',
            'session_id': 'session-1',
            'message': {
                'id': 'active-message',
                'role': 'assistant',
                'content': '这条消息应出现在当前详情区。',
            },
        })
        assert len(recorded['appended_messages']) == 1, '当前会话消息应增量追加到详情区。'

        app_instance.switch_session('session-2')
        latest_hydration = recorded['hydrate_calls'][-1]
        assert latest_hydration['active_session_id'] == 'session-2', '切换会话后应重新注水目标会话。'
        assert latest_hydration['timeline_entries'][0]['id'] == 'message-2', '切换后应展示目标会话时间线。'

        app_instance.create_session()
        latest_hydration = recorded['hydrate_calls'][-1]
        assert latest_hydration['active_session_id'] == 'session-3', '新建会话后应立即激活新会话。'
        assert latest_hydration['timeline_entries'] == [], '新建会话后右侧时间线应进入空态。'
    finally:
        if app_instance is not None and hasattr(app_instance, 'cleanup'):
            try:
                app_instance.cleanup()
            except Exception:
                pass
        setattr(app_module, 'Core', original_core)
        setattr(app_module, 'UI', original_ui)


def test_settings_compatibility_regression() -> None:
    core_module = importlib.import_module('core')
    settings_module = importlib.import_module('utils.settings')
    ui_module = importlib.import_module('ui')

    original_home = os.environ.get('HOME')
    original_llm = core_module.LLM
    original_interpreter = core_module.Interpreter

    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ['HOME'] = temp_dir

        class StubLLM:
            def __init__(self, *args, **kwargs):
                return None

            def cleanup(self) -> None:
                return None

        class StubInterpreter:
            def __init__(self, status_queue, session_store=None):
                self.status_queue = status_queue
                self.session_store = session_store

        class FakeSettings:
            def __init__(self):
                self.saved_settings = None

            def save_settings(self, settings_dict):
                self.saved_settings = dict(settings_dict)
                return dict(settings_dict)

        setattr(core_module, 'LLM', StubLLM)
        setattr(core_module, 'Interpreter', StubInterpreter)

        core_instance = None

        try:
            settings = settings_module.Settings()
            storage_paths = settings.get_storage_paths()
            assert storage_paths['settings_file'].endswith('settings.json'), '设置文件路径应指向 settings.json。'
            assert storage_paths['session_history_db'].endswith('session_history.db'), '数据库路径应指向 session_history.db。'
            assert storage_paths['settings_file'] != storage_paths['session_history_db'], '配置文件与数据库路径必须分离。'

            core_instance = core_module.Core()
            config_issue = core_instance._build_config_issue(RuntimeError('config'))
            database_issue = core_instance._build_database_issue(
                'db',
                'hint',
                RuntimeError('database'),
            )
            assert config_issue['path'] == storage_paths['config_db'], '配置错误应指向当前生效的配置存储路径。'
            assert config_issue['path'].endswith('session_history.db'), '当前配置中心应落在 session_history.db。'
            assert database_issue['path'] == storage_paths['session_history_db'], '数据库错误应指向 session_history.db。'
            assert config_issue['category'] == 'config', '配置错误应保持 config 分类。'
            assert database_issue['category'] == 'database', '数据库错误应保持 database 分类。'

            scheduled_themes: list[str] = []
            destroyed_flags: list[bool] = []

            class FakeVar:
                def __init__(self, value: Any = ''):
                    self.value = value

                def get(self):
                    return self.value

                def set(self, value):
                    self.value = value

            class FakeTextValue:
                def __init__(self, value=''):
                    self.value = value

                def get(self, *args):
                    return self.value

            class FakeMaster:
                def schedule_theme_change(self, theme_name: str) -> None:
                    scheduled_themes.append(theme_name)

            settings_window = object.__new__(ui_module.UI.SettingsWindow)
            settings_window.master = FakeMaster()
            settings_window.pending_theme_name = 'superhero'
            settings_window.theme_var = FakeVar('superhero')
            settings_window.provider_var = FakeVar('openai_compatible')
            settings_window.base_url_entry = FakeTextValue('https://api.openai.com/v1/')
            settings_window.api_key_entry = FakeTextValue('')
            settings_window.model_var = FakeVar('gpt-5.2')
            settings_window.language_var = FakeVar('简体中文')
            settings_window.enable_reasoning_var = FakeVar(0)
            settings_window.reasoning_depth_var = FakeVar('medium')
            settings_window.request_timeout_entry = FakeTextValue('25')
            settings_window.play_ding = FakeVar(0)
            settings_window.llm_instructions_text = FakeTextValue('')
            settings_window.language_options = [('zh-CN', '简体中文'), ('en-US', 'English')]
            settings_window.set_feedback = lambda *args, **kwargs: None
            settings_window.after = lambda _delay, callback: callback()
            settings_window.destroy = lambda: destroyed_flags.append(True)
            fake_settings = FakeSettings()
            settings_window.settings = fake_settings

            settings_window.theme_var.set('darkly')
            ui_module.UI.SettingsWindow.on_theme_change(settings_window)

            assert settings_window.pending_theme_name == 'darkly', '主题切换应先记录待应用主题。'
            assert scheduled_themes == [], '下拉选择主题时不应立即应用主题。'

            ui_module.UI.SettingsWindow.save_button(settings_window)

            assert fake_settings.saved_settings is not None, '保存设置时应写入设置文件。'
            assert fake_settings.saved_settings.get('theme') == 'darkly', '保存设置时应持久化待应用主题。'
            assert scheduled_themes == ['darkly'], '主题应在保存并关闭设置窗口后再统一应用。'
            assert destroyed_flags == [True], '保存设置后应关闭设置窗口。'
        finally:
            if core_instance is not None:
                try:
                    core_instance.cleanup()
                except Exception:
                    pass

            setattr(core_module, 'LLM', original_llm)
            setattr(core_module, 'Interpreter', original_interpreter)

            if original_home is None:
                os.environ.pop('HOME', None)
            else:
                os.environ['HOME'] = original_home


TEST_CASES: list[tuple[str, Callable[[], None]]] = [
    ('session_store_regression_suite', test_session_store_regression_suite),
    ('session_context_regression_suite', test_session_context_regression_suite),
    ('chat_ui_regression_suite', test_chat_ui_regression_suite),
    ('session_switch_restore_and_timeline_regression', test_session_switch_restore_and_timeline_regression),
    ('app_event_filter_and_new_session_regression', test_app_event_filter_and_new_session_regression),
    ('settings_compatibility_regression', test_settings_compatibility_regression),
]


def main() -> int:
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
