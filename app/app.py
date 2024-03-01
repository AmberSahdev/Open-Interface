import sys
import threading
from multiprocessing import freeze_support

from core import Core
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
    |  |   Executor  |                                   |
    |  +-------------+                                   |
    +----------------------------------------------------+
    """

    def __init__(self):
        self.core = Core()
        self.ui = UI()

        # Create threads to facilitate communication between core and ui through queues
        self.core_to_ui_connection_thread = threading.Thread(target=self.send_status_from_core_to_ui, daemon=True)
        self.ui_to_core_connection_thread = threading.Thread(target=self.send_user_request_from_ui_to_core, daemon=True)

    def run(self):
        self.core_to_ui_connection_thread.start()
        self.ui_to_core_connection_thread.start()

        self.ui.run()

    def send_status_from_core_to_ui(self):
        while True:
            status = self.core.status_queue.get()
            print(f'Sending status: {status}')
            self.ui.display_current_status(status)

    def send_user_request_from_ui_to_core(self):
        while True:
            user_request = self.ui.main_window.user_request_queue.get()
            print(f'Sending user request: {user_request}')

            if user_request == 'stop':
                self.core.stop_previous_request()
            else:
                threading.Thread(target=self.core.execute_user_request, args=(user_request,), daemon=True).start()


if __name__ == '__main__':
    freeze_support()  # As required by pyinstaller https://www.pyinstaller.org/en/stable/common-issues-and-pitfalls.html#multi-processing
    app = App()
    app.run()
    sys.exit(0)
