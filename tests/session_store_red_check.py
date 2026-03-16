import importlib
import os
import sqlite3
import sys
import tempfile
import traceback
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / 'app'))


REQUIRED_TABLES = {
    'sessions',
    'messages',
    'execution_logs',
}

REQUIRED_INDEXES = {
    'idx_sessions_updated_at',
    'idx_messages_session_created_at',
    'idx_execution_logs_message_step',
    'idx_execution_logs_session_created_at',
}


def load_session_store_class():
    try:
        module = importlib.import_module('session_store')
    except ModuleNotFoundError as exc:
        raise AssertionError(
            '缺少 app/session_store.py：P0-1 需要新增独立的 SQLite 持久化层。'
        ) from exc

    if not hasattr(module, 'SessionStore'):
        raise AssertionError(
            'app/session_store.py 已存在，但缺少 SessionStore 类，无法承载会话/消息/执行日志 CRUD。'
        )

    return module.SessionStore


def sqlite_objects(db_path):
    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        tables = {
            row[0]
            for row in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        indexes = {
            row[0]
            for row in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
    finally:
        connection.close()

    return tables, indexes


def test_normal_path_store_can_persist_session_message_and_log():
    session_store_class = load_session_store_class()

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / 'session_history.db'
        store = session_store_class(db_path)
        store.initialize()

        session = store.create_session('多会话红灯验证')
        assert session['title'] == '多会话红灯验证', 'create_session() 应返回新建会话标题。'

        message = store.create_message(session['id'], 'user', '你好，先保存一条消息。')
        assert message['role'] == 'user', 'create_message() 应记录消息角色。'

        execution_log = store.append_execution_log(
            session_id=session['id'],
            message_id=message['id'],
            step_index=0,
            status='started',
            justification='准备执行首个步骤',
            function_name='noop',
            parameters_json='{}',
        )
        assert execution_log['status'] == 'started', 'append_execution_log() 应返回写入结果。'

        sessions = store.list_sessions()
        messages = store.list_messages(session['id'])
        logs = store.list_execution_logs(message['id'])

        assert len(sessions) == 1, 'list_sessions() 应返回 1 条会话。'
        assert len(messages) == 1, 'list_messages() 应返回 1 条消息。'
        assert len(logs) == 1, 'list_execution_logs() 应返回 1 条执行记录。'


def test_boundary_initialize_new_database_is_idempotent_and_creates_schema():
    session_store_class = load_session_store_class()

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / 'nested' / 'session_history.db'
        store = session_store_class(db_path)

        store.initialize()
        store.initialize()

        assert db_path.exists(), 'initialize() 应自动创建数据库目录与数据库文件。'

        tables, indexes = sqlite_objects(db_path)
        missing_tables = REQUIRED_TABLES - tables
        missing_indexes = REQUIRED_INDEXES - indexes

        assert not missing_tables, f'初始化后缺少数据表：{sorted(missing_tables)}'
        assert not missing_indexes, f'初始化后缺少索引：{sorted(missing_indexes)}'


def test_negative_core_initializes_schema_before_llm_failure():
    core_module = importlib.import_module('core')

    original_home = os.environ.get('HOME')
    original_llm = core_module.LLM

    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ['HOME'] = temp_dir

        class ExplodingLLM:
            def __init__(self, *args, **kwargs):
                raise RuntimeError('forced llm failure for red test')

        setattr(core_module, 'LLM', ExplodingLLM)

        try:
            core_module.Core()
        finally:
            setattr(core_module, 'LLM', original_llm)
            if original_home is None:
                os.environ.pop('HOME', None)
            else:
                os.environ['HOME'] = original_home

        db_path = Path(temp_dir) / '.open-interface' / 'session_history.db'
        assert db_path.exists(), (
            'Core.__init__() 应在 LLM 初始化失败前先创建 ~/.open-interface/session_history.db。'
        )

        tables, indexes = sqlite_objects(db_path)
        missing_tables = REQUIRED_TABLES - tables
        missing_indexes = REQUIRED_INDEXES - indexes

        assert not missing_tables, f'Core 启动后缺少数据表：{sorted(missing_tables)}'
        assert not missing_indexes, f'Core 启动后缺少索引：{sorted(missing_indexes)}'


TEST_CASES = [
    (
        'normal_path_store_can_persist_session_message_and_log',
        test_normal_path_store_can_persist_session_message_and_log,
    ),
    (
        'boundary_initialize_new_database_is_idempotent_and_creates_schema',
        test_boundary_initialize_new_database_is_idempotent_and_creates_schema,
    ),
    (
        'negative_core_initializes_schema_before_llm_failure',
        test_negative_core_initializes_schema_before_llm_failure,
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
