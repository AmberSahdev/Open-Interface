import threading
import tkinter as tk
import webbrowser
from multiprocessing import Queue
from pathlib import Path
from tkinter import ttk

import speech_recognition as sr
from PIL import Image, ImageTk

from utils.settings import Settings
from version import version


def open_link(url) -> None:
    webbrowser.open_new(url)


class UI:
    def __init__(self):
        self.main_window = self.MainWindow()

    def run(self) -> None:
        self.main_window.mainloop()

    def display_current_status(self, text: str):
        self.main_window.update_message(text)

    class AdvancedSettingsWindow(tk.Toplevel):
        """
        Self-contained settings sub-window for the UI
        """

        def __init__(self, parent):
            super().__init__(parent)
            self.title('Advanced Settings')
            self.minsize(300, 300)
            self.create_widgets()
            self.settings = Settings()

            # Populate UI
            settings_dict = self.settings.get_dict()

            if 'base_url' in settings_dict:
                self.base_url_entry.insert(0, settings_dict['base_url'])
            if 'model' in settings_dict:
                self.model_entry.insert(0, settings_dict['model'])

        def create_widgets(self) -> None:
            label_base_url = tk.Label(self, text='Custom OpenAI-Like API Model Base URL')
            label_base_url.pack(pady=10)

            # Entry for Base URL
            self.base_url_entry = ttk.Entry(self, width=30)
            self.base_url_entry.pack()

            # Model Label
            label_model = tk.Label(self, text='Custom Model Name:')
            label_model.pack(pady=10)

            # Entry for Model
            self.model_entry = ttk.Entry(self, width=30)
            self.model_entry.pack()

            # Save Button
            save_button = ttk.Button(self, text='Save Settings', command=self.save_button)
            save_button.pack(pady=20)

        def save_button(self) -> None:
            base_url = self.base_url_entry.get().strip()
            model = self.model_entry.get().strip()
            settings_dict = {
                "base_url": base_url,
                "model": model,
            }

            self.settings.save_settings_to_file(settings_dict)
            self.destroy()

    class SettingsWindow(tk.Toplevel):
        """
        Self-contained settings sub-window for the UI
        """

        def __init__(self, parent):
            super().__init__(parent)
            self.title('Settings')
            self.minsize(300, 450)
            self.create_widgets()

            self.settings = Settings()

            # Populate UI
            settings_dict = self.settings.get_dict()

            if 'api_key' in settings_dict:
                self.api_key_entry.insert(0, settings_dict['api_key'])
            if 'default_browser' in settings_dict:
                self.browser_combobox.set(settings_dict['default_browser'])
            if 'play_ding_on_completion' in settings_dict:
                self.play_ding.set(1 if settings_dict['play_ding_on_completion'] else 0)
            if 'custom_llm_instructions' in settings_dict:
                self.llm_instructions_text.insert('1.0', settings_dict['custom_llm_instructions'])

        def create_widgets(self) -> None:
            # Label for API Key
            label_api = tk.Label(self, text='OpenAI API Key:')
            label_api.pack(pady=10)

            # Entry for API Key
            self.api_key_entry = ttk.Entry(self, width=30)
            self.api_key_entry.pack()

            # Label for Browser Choice
            label_browser = tk.Label(self, text='Choose Default Browser:')
            label_browser.pack(pady=10)

            # Dropdown for Browser Choice
            self.browser_var = tk.StringVar()
            self.browser_combobox = ttk.Combobox(self, textvariable=self.browser_var,
                                                 values=['Safari', 'Firefox', 'Chrome'])
            self.browser_combobox.pack(pady=5)
            self.browser_combobox.set('Choose Browser')

            # Label for Custom LLM Instructions
            label_llm = tk.Label(self, text='Custom LLM Instructions:')
            label_llm.pack(pady=10)

            # Text Box for Custom LLM Instructions
            self.llm_instructions_text = tk.Text(self, height=5, width=40)
            self.llm_instructions_text.pack(pady=5)

            # Checkbox for "Play Ding" option
            self.play_ding = tk.IntVar()
            play_ding_checkbox = ttk.Checkbutton(self, text="Play Ding on Completion", variable=self.play_ding)
            play_ding_checkbox.pack(pady=10)

            # Save Button
            save_button = ttk.Button(self, text='Save Settings', command=self.save_button)
            save_button.pack(pady=(10, 0))

            # Button to open Advanced Settings
            advanced_settings_button = ttk.Button(self, text='Advanced Settings', command=self.open_advanced_settings)
            advanced_settings_button.pack(pady=(0, 10))

            # Hyperlink Label
            link_label = tk.Label(self, text='Instructions', fg='#499CE4')
            link_label.pack()
            link_label.bind('<Button-1>', lambda e: open_link(
                'https://github.com/AmberSahdev/Open-Interface?tab=readme-ov-file#setup-%EF%B8%8F'))
            
            # Check for Updates Label
            update_label = tk.Label(self, text='Check for Updates', fg='#499CE4', font=('Helvetica', 10))
            update_label.pack()
            update_label.bind('<Button-1>', lambda e: open_link(
                'https://github.com/AmberSahdev/Open-Interface/releases/latest'))

            # Version Label
            version_label = tk.Label(self, text=f'Version: {str(version)}', font=('Helvetica', 10))
            version_label.pack(side="bottom", pady=10)

        def save_button(self) -> None:
            api_key = self.api_key_entry.get().strip()
            default_browser = self.browser_var.get()
            settings_dict = {
                'api_key': api_key,
                'default_browser': default_browser,
                'play_ding_on_completion': bool(self.play_ding.get()),
                'custom_llm_instructions': self.llm_instructions_text.get("1.0", "end-1c").strip()
            }

            self.settings.save_settings_to_file(settings_dict)
            self.destroy()

        def open_advanced_settings(self):
            # Open the advanced settings window
            UI.AdvancedSettingsWindow(self)

    class MainWindow(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title('Open Interface')
            self.minsize(420, 250)

            # PhotoImage object needs to persist as long as the app does, hence it's a class object.
            path_to_icon_png = Path(__file__).resolve().parent.joinpath('resources', 'icon.png')
            path_to_microphone_png = Path(__file__).resolve().parent.joinpath('resources', 'microphone.png')
            self.logo_img = ImageTk.PhotoImage(Image.open(path_to_icon_png).resize((50, 50)))
            self.mic_icon = ImageTk.PhotoImage(Image.open(path_to_microphone_png).resize((18, 18)))

            # This adds app icon in linux which pyinstaller can't
            self.tk.call('wm', 'iconphoto', self._w, self.logo_img)

            # MP Queue to facilitate communication between UI and Core.
            # Put user requests received from UI text box into this queue which will then be dequeued in App to be sent
            # to core.
            self.user_request_queue = Queue()

            self.create_widgets()

        def create_widgets(self) -> None:
            # Creates and arranges the UI elements
            # Frame
            frame = ttk.Frame(self, padding='10 10 10 10')
            frame.grid(column=0, row=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            frame.columnconfigure(0, weight=1)

            logo_label = tk.Label(frame, image=self.logo_img)
            logo_label.grid(column=0, row=0, sticky=tk.W, pady=(10, 20))

            # Heading Label
            heading_label = tk.Label(frame, text='What would you like me to do?', font=('Helvetica', 16),
                                     wraplength=400)
            heading_label.grid(column=0, row=1, columnspan=3, sticky=tk.W)

            # Entry widget
            self.entry = ttk.Entry(frame, width=30)
            self.entry.grid(column=0, row=2, sticky=(tk.W, tk.E))

            # Submit Button
            button = ttk.Button(frame, text='Submit', command=self.execute_user_request)
            button.grid(column=2, row=2)

            # Mic Button
            mic_button = tk.Button(frame, image=self.mic_icon, command=self.start_voice_input_thread, borderwidth=0,
                                   highlightthickness=0)
            mic_button.grid(column=1, row=2, padx=(0, 5))

            # Settings Button
            settings_button = ttk.Button(self, text='Settings', command=self.open_settings)
            settings_button.place(relx=1.0, rely=0.0, anchor='ne', x=-5, y=5)

            # Stop Button
            stop_button = ttk.Button(self, text='Stop', command=self.stop_previous_request)
            stop_button.place(relx=1.0, rely=1.0, anchor='se', x=-10, y=-10)

            # Text display for echoed input
            self.input_display = tk.Label(frame, text='', font=('Helvetica', 16), wraplength=400)
            self.input_display.grid(column=0, row=3, columnspan=3, sticky=tk.W)

            # Text display for additional messages
            self.message_display = tk.Label(frame, text='', font=('Helvetica', 14))
            self.message_display.grid(column=0, row=6, columnspan=3, sticky=tk.W)

        def open_settings(self) -> None:
            UI.SettingsWindow(self)

        def stop_previous_request(self) -> None:
            # Interrupt currently running request by queueing a stop signal.
            self.user_request_queue.put('stop')

        def display_input(self) -> str:
            # Get the entry and update the input display
            user_input = self.entry.get()
            self.input_display['text'] = f'{user_input}'

            # Clear the entry widget
            self.entry.delete(0, tk.END)

            return user_input.strip()

        def execute_user_request(self) -> None:
            # Puts the user request received from the UI into the MP queue being read in App to be sent to Core.
            user_request = self.display_input()

            if user_request == '' or user_request is None:
                return

            self.update_message('Fetching Instructions')

            self.user_request_queue.put(user_request)

        def start_voice_input_thread(self) -> None:
            # Start voice input in a separate thread
            threading.Thread(target=self.voice_input, daemon=True).start()

        def voice_input(self) -> None:
            # Function to handle voice input
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                self.update_message('Listening...')
                recognizer.adjust_for_ambient_noise(source) # This might also help with asking for mic permissions on Macs
                try:
                    audio = recognizer.listen(source, timeout=4)
                    try:
                        text = recognizer.recognize_google(audio)
                        self.entry.delete(0, tk.END)
                        self.entry.insert(0, text)
                        self.update_message('')
                    except sr.UnknownValueError:
                        self.update_message('Could not understand audio')
                    except sr.RequestError as e:
                        self.update_message(f'Could not request results - {e}')
                except sr.WaitTimeoutError:
                    self.update_message('Didn\'t hear anything')

        def update_message(self, message: str) -> None:
            # Update the message display with the provided text.
            # Ensure thread safety when updating the Tkinter GUI.
            if threading.current_thread() is threading.main_thread():
                self.message_display['text'] = message
            else:
                self.message_display.after(0, lambda: self.message_display.config(text=message))
