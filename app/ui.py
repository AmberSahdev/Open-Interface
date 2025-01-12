import threading
import webbrowser
from multiprocessing import Queue
from pathlib import Path

# import speech_recognition as sr
import ttkbootstrap as ttk
from PIL import Image, ImageTk

from llm import DEFAULT_MODEL_NAME
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

    class AdvancedSettingsWindow(ttk.Toplevel):
        """
        Self-contained settings sub-window for the UI
        """

        def __init__(self, parent):
            super().__init__(parent)
            self.title('Advanced Settings')
            self.minsize(300, 300)
            self.settings = Settings()
            self.create_widgets()

            # Populate UI
            settings_dict = self.settings.get_dict()

            if 'base_url' in settings_dict:
                self.base_url_entry.insert(0, settings_dict['base_url'])
            if 'model' in settings_dict:
                self.model_entry.insert(0, settings_dict['model'])
                self.model_var.set(settings_dict.get('model', 'custom'))
            else:
                self.model_entry.insert(0, DEFAULT_MODEL_NAME)
                self.model_var.set(DEFAULT_MODEL_NAME)

        def create_widgets(self) -> None:
            # Radio buttons for model selection
            ttk.Label(self, text='Select Model:', bootstyle="primary").pack(pady=10, padx=10)
            self.model_var = ttk.StringVar(value='custom')  # default selection

            # Create a frame to hold the radio buttons
            radio_frame = ttk.Frame(self)
            radio_frame.pack(padx=20, pady=10)  # Add padding around the frame

            models = [
                ('GPT-4o (Default. Medium-Accurate, Medium-Fast)', 'gpt-4o'),
                ('GPT-4o-mini (Cheapest, Fastest)', 'gpt-4o-mini'),
                ('GPT-4v (Deprecated. Most-Accurate, Slowest)', 'gpt-4-vision-preview'),
                ('GPT-4-Turbo (Least Accurate, Fast)', 'gpt-4-turbo'),
                ('Custom (Specify Settings Below)', 'custom')
            ]
            for text, value in models:
                ttk.Radiobutton(radio_frame, text=text, value=value, variable=self.model_var, bootstyle="info").pack(
                    anchor=ttk.W, pady=5)

            label_base_url = ttk.Label(self, text='Custom OpenAI-Like API Model Base URL', bootstyle="secondary")
            label_base_url.pack(pady=10)

            # Entry for Base URL
            self.base_url_entry = ttk.Entry(self, width=30)
            self.base_url_entry.pack()

            # Model Label
            label_model = ttk.Label(self, text='Custom Model Name:', bootstyle="secondary")
            label_model.pack(pady=10)

            # Entry for Model
            self.model_entry = ttk.Entry(self, width=30)
            self.model_entry.pack()

            # Save Button
            save_button = ttk.Button(self, text='Save Settings', bootstyle="success", command=self.save_button)
            save_button.pack(pady=20)

        def save_button(self) -> None:
            base_url = self.base_url_entry.get().strip()
            model = self.model_var.get() if self.model_var.get() != 'custom' else self.model_entry.get().strip()
            settings_dict = {
                'base_url': base_url,
                'model': model,
            }

            self.settings.save_settings_to_file(settings_dict)
            self.destroy()

    class SettingsWindow(ttk.Toplevel):
        """
        Self-contained settings sub-window for the UI
        """

        def __init__(self, parent):
            super().__init__(parent)
            self.title('Settings')
            self.minsize(300, 450)
            self.available_themes = ['darkly', 'cyborg', 'journal', 'solar', 'superhero']
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
            if 'custom_llm_instructions':
                self.llm_instructions_text.insert('1.0', settings_dict['custom_llm_instructions'])
            self.theme_combobox.set(settings_dict.get('theme', 'superhero'))

        def create_widgets(self) -> None:
            # API Key Widgets
            label_api = ttk.Label(self, text='OpenAI API Key:', bootstyle="info")
            label_api.pack(pady=10)
            self.api_key_entry = ttk.Entry(self, width=30)
            self.api_key_entry.pack()

            # Label for Browser Choice
            label_browser = ttk.Label(self, text='Choose Default Browser:', bootstyle="info")
            label_browser.pack(pady=10)

            # Dropdown for Browser Choice
            self.browser_var = ttk.StringVar()
            self.browser_combobox = ttk.Combobox(self, textvariable=self.browser_var,
                                                 values=['Safari', 'Firefox', 'Chrome'])
            self.browser_combobox.pack(pady=5)
            self.browser_combobox.set('Choose Browser')

            # Label for Custom LLM Guidance
            label_llm = ttk.Label(self, text='Custom LLM Guidance:', bootstyle="info")
            label_llm.pack(pady=10)

            # Text Box for Custom LLM Instructions
            self.llm_instructions_text = ttk.Text(self, height=10, width=50)
            self.llm_instructions_text.pack(padx=(10, 10), pady=(0, 10))

            # Checkbox for "Play Ding" option
            self.play_ding = ttk.IntVar()
            play_ding_checkbox = ttk.Checkbutton(self, text="Play Ding on Completion", variable=self.play_ding,
                                                 bootstyle="round-toggle")
            play_ding_checkbox.pack(pady=10)

            # Theme Selection Widgets
            label_theme = ttk.Label(self, text='UI Theme:', bootstyle="info")
            label_theme.pack()
            self.theme_var = ttk.StringVar()
            self.theme_combobox = ttk.Combobox(self, textvariable=self.theme_var, values=self.available_themes,
                                               state="readonly")
            self.theme_combobox.pack(pady=5)
            self.theme_combobox.set('superhero')
            # Add binding for immediate theme change
            self.theme_combobox.bind('<<ComboboxSelected>>', self.on_theme_change)

            # Save Button
            save_button = ttk.Button(self, text='Save Settings', bootstyle="success", command=self.save_button)
            save_button.pack(pady=(10, 5))

            # Button to open Advanced Settings
            advanced_settings_button = ttk.Button(self, text='Advanced Settings', bootstyle="info",
                                                  command=self.open_advanced_settings)
            advanced_settings_button.pack(pady=(0, 10))

            # Hyperlink Label
            link_label = ttk.Label(self, text='Setup Instructions', bootstyle="primary")
            link_label.pack()
            link_label.bind('<Button-1>', lambda e: open_link(
                'https://github.com/AmberSahdev/Open-Interface?tab=readme-ov-file#setup-%EF%B8%8F'))

            # Check for updates Label
            update_label = ttk.Label(self, text='Check for Updates', bootstyle="primary")
            update_label.pack()
            update_label.bind('<Button-1>', lambda e: open_link(
                'https://github.com/AmberSahdev/Open-Interface/releases/latest'))

            # Version Label
            version_label = ttk.Label(self, text=f'Version: {str(version)}', font=('Helvetica', 10))
            version_label.pack(side="bottom", pady=10)

        def on_theme_change(self, event=None) -> None:
            # Apply theme immediately when selected
            theme = self.theme_var.get()
            self.master.change_theme(theme)

        def save_button(self) -> None:
            theme = self.theme_var.get()
            api_key = self.api_key_entry.get().strip()
            default_browser = self.browser_var.get()
            settings_dict = {
                'api_key': api_key,
                'default_browser': default_browser,
                'play_ding_on_completion': bool(self.play_ding.get()),
                'custom_llm_instructions': self.llm_instructions_text.get("1.0", "end-1c").strip(),
                'theme': theme
            }

            # Remove redundant theme change since it's already applied
            self.settings.save_settings_to_file(settings_dict)
            self.destroy()

        def open_advanced_settings(self):
            # Open the advanced settings window
            UI.AdvancedSettingsWindow(self)

    class MainWindow(ttk.Window):
        def change_theme(self, theme_name: str) -> None:
            self.style.theme_use(theme_name)

        def __init__(self):
            settings = Settings()
            settings_dict = settings.get_dict()
            theme = settings_dict.get('theme', 'superhero')

            try:
                super().__init__(themename=theme)
            except:
                super().__init__()  # https://github.com/AmberSahdev/Open-Interface/issues/35  

            self.title('Open Interface')
            window_width = 450
            window_height = 270
            self.minsize(window_width, window_height)

            # Set the geometry of the window
            # Calculate position for bottom right corner
            screen_width = self.winfo_screenwidth()
            x_position = screen_width - window_width - 10  # 10px margin from the right edge
            y_position = 50  # 50px margin from the bottom edge
            self.geometry(f'{window_width}x{window_height}+{x_position}+{y_position}')

            # PhotoImage object needs to persist as long as the app does, hence it's a class object.
            path_to_icon_png = Path(__file__).resolve().parent.joinpath('resources', 'icon.png')
            # path_to_microphone_png = Path(__file__).resolve().parent.joinpath('resources', 'microphone.png')
            self.logo_img = ImageTk.PhotoImage(Image.open(path_to_icon_png).resize((50, 50)))
            # self.mic_icon = ImageTk.PhotoImage(Image.open(path_to_microphone_png).resize((18, 18)))

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
            frame.grid(column=0, row=0, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))
            frame.columnconfigure(0, weight=1)

            logo_label = ttk.Label(frame, image=self.logo_img)
            logo_label.grid(column=0, row=0, sticky=ttk.W, pady=(10, 20))

            # Heading Label
            heading_label = ttk.Label(frame, text='What would you like me to do?', font=('Helvetica', 16),
                                      bootstyle="primary",
                                      wraplength=300)
            heading_label.grid(column=0, row=1, columnspan=3, sticky=ttk.W)

            # Entry widget
            self.entry = ttk.Entry(frame, width=38)
            self.entry.grid(column=0, row=2, sticky=(ttk.W, ttk.E))

            # Bind the Enter key to the submit function
            self.entry.bind("<Return>", lambda event: self.execute_user_request())
            self.entry.bind("<KP_Enter>", lambda event: self.execute_user_request())

            # Mic Button
            # mic_button = ttk.Button(frame, image=self.mic_icon, bootstyle="link", command=self.start_voice_input_thread)
            # mic_button.grid(column=1, row=2, padx=(0, 5))

            # Submit Button
            button = ttk.Button(frame, text='Submit', bootstyle="success", command=self.execute_user_request)
            button.grid(column=2, row=2, padx=10)

            # Settings Button
            settings_button = ttk.Button(self, text='Settings', bootstyle="info-outline", command=self.open_settings)
            settings_button.place(relx=1.0, rely=0.0, anchor='ne', x=-5, y=5)

            # Stop Button
            stop_button = ttk.Button(self, text='Stop', bootstyle="danger-outline", command=self.stop_previous_request)
            stop_button.place(relx=1.0, rely=1.0, anchor='se', x=-10, y=-10)

            # Text display for echoed input
            self.input_display = ttk.Label(frame, text='', font=('Helvetica', 16), wraplength=400)
            self.input_display.grid(column=0, row=3, columnspan=3, sticky=ttk.W)

            # Text display for additional messages
            self.message_display = ttk.Label(frame, text='', font=('Helvetica', 14), wraplength=400)
            self.message_display.grid(column=0, row=6, columnspan=3, sticky=ttk.W)

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
            self.entry.delete(0, ttk.END)

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
            # Currently commented out because the speech_recognition library doesn't compile well on MacOS.
            # TODO: Replace with an alternative library
            """
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                self.update_message('Listening...')
                # This might also help with asking for mic permissions on Macs
                recognizer.adjust_for_ambient_noise(source)
                try:
                    audio = recognizer.listen(source, timeout=4)
                    try:
                        text = recognizer.recognize_google(audio)
                        self.entry.delete(0, ttk.END)
                        self.entry.insert(0, text)
                        self.update_message('')
                    except sr.UnknownValueError:
                        self.update_message('Could not understand audio')
                    except sr.RequestError as e:
                        self.update_message(f'Could not request results - {e}')
                except sr.WaitTimeoutError:
                    self.update_message('Didn\'t hear anything')
            """

        def update_message(self, message: str) -> None:
            # Update the message display with the provided text.
            # Ensure thread safety when updating the Tkinter GUI.
            if threading.current_thread() is threading.main_thread():
                self.message_display['text'] = message
            else:
                self.message_display.after(0, lambda: self.message_display.config(text=message))
