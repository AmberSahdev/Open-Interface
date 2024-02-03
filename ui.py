import tkinter as tk
from tkinter import ttk
import speech_recognition as sr
import threading
from PIL import Image, ImageTk
import webbrowser

def open_link(url):
    webbrowser.open_new(url)  # Replace with your desired URL

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("300x150")
        self.create_widgets()

    def create_widgets(self):
        # Label
        label = tk.Label(self, text="OpenAI API Key:")
        label.pack(pady=10)

        # Entry for API Key
        self.api_key_entry = ttk.Entry(self, width=30)
        self.api_key_entry.pack()

        # Button to set API Key
        set_button = ttk.Button(self, text="Set OpenAI API Key", command=self.set_api_key)
        set_button.pack(pady=10)

        # Hyperlink Label
        link_label = tk.Label(self, text="Instructions", fg="#499CE4", cursor="hand")
        link_label.pack()
        link_label.bind("<Button-1>", lambda e: open_link("https://www.AmberSah.dev"))

    def set_api_key(self):
        # Function to handle setting of API Key
        api_key = self.api_key_entry.get()
        # Here you can add code to save the API key or use it as needed
        print(f"API Key set to: {api_key}")  # For demonstration
        self.destroy()

class TkinterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Open Interface")
        self.minsize(450, 250)
        self.maxsize(450, 250)
        self.create_widgets()

    def create_widgets(self):
        # Frame
        frame = ttk.Frame(self, padding="10 10 10 10")
        frame.grid(column=0, row=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        frame.columnconfigure(0, weight=1)

        self.logo_img = ImageTk.PhotoImage(Image.open("global.png").resize((50, 50))) # PhotoImage object needs to persist as long as the app does
        logo_label = tk.Label(frame, image=self.logo_img)
        logo_label.grid(column=0, row=0, sticky=tk.W, pady=(10, 10))

        # Heading Label
        heading_label = tk.Label(frame, text="Enter Command Below:", font=('Helvetica', 16))
        heading_label.grid(column=0, row=1, columnspan=3, sticky=tk.W)

        # Entry widget
        self.entry = ttk.Entry(frame, width=25)
        self.entry.grid(column=0, row=2, sticky=(tk.W, tk.E))

        # Submit Button
        button = ttk.Button(frame, text="Submit", command=self.display_input)
        button.grid(column=2, row=2)

        # Mic Button
        self.mic_icon = ImageTk.PhotoImage(Image.open("microphone2.png").resize((20, 20)))
        mic_button = tk.Button(frame, image=self.mic_icon, command=self.start_voice_input_thread)
        mic_button.grid(column=1, row=2)

        # Settings Button
        settings_button = ttk.Button(self, text="Settings", command=self.open_settings)
        settings_button.place(relx=1.0, rely=0.0, anchor='ne', x=-5, y=5)

        # Text display for echoed input
        self.input_display = tk.Label(frame, text="", font=('Helvetica', 16))
        self.input_display.grid(column=0, row=3, columnspan=3, sticky=tk.W)

        # Text display for additional messages
        self.message_display = tk.Label(frame, text="", font=('Helvetica', 16))
        self.message_display.grid(column=0, row=4, columnspan=3, sticky=tk.W)

    def open_settings(self):
        # Function to open the settings window
        SettingsWindow(self)

    def display_input(self):
        # Get the entry and update the input display
        user_input = self.entry.get()
        self.input_display['text'] = f"{user_input}"

        # Clear the entry widget
        self.entry.delete(0, tk.END)

    def start_voice_input_thread(self):
        # Start voice input in a separate thread
        threading.Thread(target=self.voice_input, daemon=True).start()

    def voice_input(self):
        # Function to handle voice input
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            self.update_message("Listening...")
            audio = recognizer.listen(source)
            try:
                text = recognizer.recognize_google(audio)
                self.entry.delete(0, tk.END)
                self.entry.insert(0, text)
                self.update_message("Voice input received.")
            except sr.UnknownValueError:
                self.update_message("Could not understand audio")
            except sr.RequestError as e:
                self.update_message(f"Could not request results; {e}")

    def update_message(self, message):
        # Update the message display with the provided text
        # Ensure thread safety when updating the Tkinter GUI
        if threading.current_thread() is threading.main_thread():
            self.message_display['text'] = message
        else:
            self.message_display.after(0, lambda: self.message_display.config(text=message))


if __name__ == "__main__":
    app = TkinterApp()
    app.mainloop()
