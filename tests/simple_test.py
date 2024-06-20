import os
import sys
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

from app import App

from multiprocessing import freeze_support


def main():
    app = App()
    threading.Thread(target=simple_test, args=(app,), daemon=True).start()
    app.run()


def simple_test(app):
    # Says hi, waits 12 seconds, requests to open chrome
    time.sleep(1)
    put_requests_in_app(app, 'Hello')
    time.sleep(12)
    put_requests_in_app(app, 'Open Chrome')


def put_requests_in_app(app, request):
    app.ui.main_window.user_request_queue.put(request)


if __name__ == '__main__':
    freeze_support()  # As required by pyinstaller https://www.pyinstaller.org/en/stable/common-issues-and-pitfalls.html#multi-processing
    main()
    sys.exit(0)
