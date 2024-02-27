"""
Can never get pyisntaller to work

NOTES:
    1. extra steps before using multiprocessing might be required https://www.pyinstaller.org/en/stable/common-issues-and-pitfalls.html#why-is-calling-multiprocessing-freeze-support-required
"""

import PyInstaller.__main__
import platform
import os

def build():
    # Path to your main application script
    app_script = os.path.join('app', 'app.py')
    print(f'app_script:{app_script}')

    # Common PyInstaller options
    pyinstaller_options = [
        '--clean',
        '--noconfirm',
        '--debug=all',
        '--onefile',
        '--paths=./venv/lib/python3.9/site-packages',
        '--paths=/usr/local/lib/python3.9/site-packages',
        '--hidden-import=pyautogui',
        '--hidden-import=openai',
        '--hidden-import=appdirs',
        '--hidden-import=pyparsing',
        '--hidden-import=pyaudio',
        '--hidden-import=speech_recognition',
        # '--windowed',  # Remove this if your application is a console program
        '--name=Open Interface',
        '--add-data=app/resources/icon.png:resources',
        '--add-data=app/resources/microphone.png:resources',
        '--add-data=app/resources/context.txt:resources',
        '--add-data=app/core.py:.',
        '--add-data=app/interpreter.py:.',
        '--add-data=app/llm.py:.',
        '--add-data=app/ui.py:.',
        '--add-data=app/utils/settings.py:utils',
        '--add-data=app/utils/screen.py:utils',
        '--add-data=app/utils/local_info.py:utils',
        app_script
    ]

    """
    # Platform-specific options
    if platform.system() == 'Windows':
        pyinstaller_options.extend([
            '--onefile',  # Uncomment this if you want a single executable file
            # '--icon=someicon.ico'  # Path to an icon file for the Windows executable
        ])
    elif platform.system() == 'Darwin':  # macOS
        pyinstaller_options.extend([
            '--onefile',  # Uncomment this if you want a single executable file
            # '--icon=someicon.icns'  # Path to an icon file for the macOS executable
        ])
    elif platform.system() == 'Linux':
        pyinstaller_options.extend([
            '--onefile',  # Uncomment this if you want a single executable file
            # Additional Linux-specific options here
        ])
    """

    # Run PyInstaller with the specified options
    #PyInstaller.__main__.run(['-v'])
    print("\n")
    PyInstaller.__main__.run(pyinstaller_options)


if __name__ == "__main__":
    build()
