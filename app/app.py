import sys
import threading
from multiprocessing import freeze_support

from core import Core
from platform_support.screen_adapter import initialize_platform_runtime
from ui import UI


class App:
    """
    +----------------------------------------------------+
    | App                                                |
    |                                                    |
    |    +-------+                                       |
    |    |  GUI  |                                       |
    |    +-------+                                       |
    |        ^                                           |
    |        | (via MP Queues)                           |
    |        v                                           |
    |  +-----------+  (Screenshot + Goal)  +-----------+ |
    |  |           | --------------------> |           | |
    |  |    Core   |                       |    LLM    | |
    |  |           | <-------------------- |  (GPT-4V) | |
    |  +-----------+    (Instructions)     +-----------+ |
    |        |                                           |
    |        v                                           |
    |  +-------------+                                   |
    |  | Interpreter |                                   |
    |  +-------------+                                   |
    |        |                                           |
    |        v                                           |
    |  +-------------+                                   |
    |  |   Executer  |                                   |
    |  +-------------+                                   |
    +----------------------------------------------------+
    """

    def __init__(self):
        initialize_platform_runtime()
        self.core = Core()
        self.ui = UI()
        self.hydrate_initial_session_view()

        # Create threads to facilitate communication between core and ui through queues
        self.core_to_ui_connection_thread = threading.Thread(target=self.send_status_from_core_to_ui, daemon=True)
        self.ui_to_core_connection_thread = threading.Thread(target=self.send_user_request_from_ui_to_core, daemon=True)

    def hydrate_initial_session_view(self) -> None:
        self.hydrate_session_view(getattr(self.core, 'active_session_id', None))
        startup_issue = self.core.get_startup_issue()
        if startup_issue is not None:
            self.ui.set_runtime_status(startup_issue)

    def hydrate_session_view(self, session_id: str | None, runtime_status: str = '') -> None:
        session_store = getattr(self.core, 'session_store', None)
        if session_store is None:
            self.ui.hydrate_session_view(None, [], [], runtime_status)
            return

        try:
            active_session_id = session_id
            if active_session_id is None:
                active_session_id = getattr(self.core, 'active_session_id', None)

            timeline_entries = []
            if active_session_id is not None:
                timeline_entries = session_store.list_timeline_entries(active_session_id)

            sessions = session_store.list_sessions()

            main_window = getattr(self.ui, 'main_window', None)
            if main_window is not None:
                setattr(main_window, 'active_session_id', active_session_id)

            hydrate_session_view = getattr(self.ui, 'hydrate_session_view', None)
            if callable(hydrate_session_view):
                hydrate_session_view(
                    active_session_id,
                    sessions,
                    timeline_entries,
                    runtime_status,
                )
                return

            self.ui.load_session_list(sessions)
            self.ui.load_timeline_history(timeline_entries)
            self.ui.set_runtime_status(runtime_status)
        except Exception as e:
            issue = self.core.build_session_view_issue(e)
            self.ui.hydrate_session_view(None, [], [], runtime_status)
            self.ui.set_runtime_status(issue)

    def refresh_session_list(self) -> None:
        session_store = getattr(self.core, 'session_store', None)
        if session_store is None:
            return

        try:
            self.ui.load_session_list(session_store.list_sessions())
        except Exception as e:
            self.ui.set_runtime_status(self.core.build_session_view_issue(e))

    def handle_core_event(self, event: dict) -> None:
        event_type = event.get('type')
        session_id = event.get('session_id')
        active_session_id = getattr(self.core, 'active_session_id', None)

        if event_type == 'runtime_status':
            if session_id is None or session_id == active_session_id:
                self.ui.set_runtime_status(event)
            return

        if event_type == 'message_persisted':
            self.refresh_session_list()
            if session_id == active_session_id:
                self.ui.append_message_item(event.get('message', {}))
            return

        if event_type == 'execution_log_persisted':
            self.refresh_session_list()
            if session_id == active_session_id:
                self.ui.append_execution_log_item(event.get('execution_log', {}))
            return

    def switch_session(self, session_id: str) -> None:
        changed = self.core.switch_active_session(session_id)
        if changed:
            self.hydrate_session_view(self.core.get_active_session_id())

    def create_session(self) -> None:
        session = self.core.create_session_and_activate()
        self.hydrate_session_view(session.get('id'))

    def run(self) -> None:
        self.core_to_ui_connection_thread.start()
        self.ui_to_core_connection_thread.start()

        self.ui.run()

    def send_status_from_core_to_ui(self) -> None:
        while True:
            status = self.core.status_queue.get()
            print(f'Sending status from thread - thread: {threading.current_thread().name}, status: {status}')
            if isinstance(status, dict):
                self.handle_core_event(status)
            else:
                self.ui.display_current_status(status)

    def send_user_request_from_ui_to_core(self) -> None:
        while True:
            user_request = self.ui.main_window.user_request_queue.get()
            print(f'Sending user request: {user_request}')

            if user_request == 'stop':
                self.core.stop_previous_request()
                continue

            elif isinstance(user_request, dict):
                action_type = user_request.get('type')

                try:
                    if action_type == 'switch_session':
                        self.switch_session(str(user_request.get('session_id') or ''))
                    elif action_type == 'create_session':
                        self.create_session()
                    elif action_type == 'interrupt_request':
                        self.core.stop_previous_request(announce=True)
                    elif action_type == 'restart_request':
                        threading.Thread(target=self.core.restart_last_request, daemon=True).start()
                    elif action_type == 'settings_updated':
                        reload_result = self.core.reload_runtime_settings()
                        if isinstance(reload_result, dict) and not reload_result.get('ok', False):
                            issue_payload = reload_result.get('issue')
                            if isinstance(issue_payload, dict):
                                self.ui.set_runtime_status(issue_payload)
                except Exception as e:
                    if action_type == 'switch_session':
                        self.ui.set_runtime_status(self.core.build_session_operation_issue('switch_session', e))
                    elif action_type == 'create_session':
                        self.ui.set_runtime_status(self.core.build_session_operation_issue('create_session', e))
            else:
                threading.Thread(target=self.core.execute_user_request, args=(user_request,), daemon=True).start()

    def cleanup(self):
        self.core.cleanup()


if __name__ == '__main__':
    freeze_support()  # As required by pyinstaller https://www.pyinstaller.org/en/stable/common-issues-and-pitfalls.html#multi-processing
    app = App()
    app.run()
    app.cleanup()
    sys.exit(0)
