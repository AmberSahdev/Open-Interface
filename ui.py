import tkinter as tk
from tkinter import ttk
import speech_recognition as sr
from PIL import Image, ImageTk
import threading

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

        # Heading Label
        heading_label = tk.Label(frame, text="Enter Command Below:", font=('Helvetica', 16))
        heading_label.grid(column=0, row=0, columnspan=3, sticky=tk.W)

        # Entry widget
        self.entry = ttk.Entry(frame, width=25)
        self.entry.grid(column=0, row=1, sticky=(tk.W, tk.E))

        # Submit Button
        button = ttk.Button(frame, text="Submit", command=self.display_input)
        button.grid(column=2, row=1)

        # Microphone Button
        #self.microphone_icon = ImageTk.PhotoImage(Image.open("microphone_icon.png").resize((20, 20)))
        #mic_button = ttk.Button(frame, image=self.microphone_icon, command=self.start_voice_input_thread)
        mic_button = ttk.Button(frame, text="Voice", command=self.start_voice_input_thread)
        mic_button.grid(column=1, row=1)

        # Text display for echoed input
        self.input_display = tk.Label(frame, text="", font=('Helvetica', 16))
        self.input_display.grid(column=0, row=3, columnspan=3, sticky=tk.W)

        # Text display for additional messages
        self.message_display = tk.Label(frame, text="", font=('Helvetica', 16))
        self.message_display.grid(column=0, row=4, columnspan=3, sticky=tk.W)

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
