import os
import sys
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

from app import App

from multiprocessing import freeze_support


def main():
    # Says hi, waits 12 seconds, requests to open chrome
    app = App()
    threading.Thread(target=put_requests_in_app, args=(app,), daemon=True).start()
    app.run()
    return


def put_requests_in_app(app):
    app.ui.main_window.user_request_queue.put('hi there')
    time.sleep(12)
    app.ui.main_window.user_request_queue.put('open chrome')


if __name__ == '__main__':
    freeze_support()  # As required by pyinstaller https://www.pyinstaller.org/en/stable/common-issues-and-pitfalls.html#multi-processing
    main()
    sys.exit(0)
