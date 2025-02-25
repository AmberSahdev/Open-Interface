import pyaudio
import wave
import whisper
import tempfile
import os

# Set PulseAudio device index (from pactl list sources short)
DEVICE_INDEX = 18  # Change this if needed

# Load Whisper model once (to avoid reloading every time)
model = whisper.load_model("medium")

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open the audio stream
stream = p.open(format=pyaudio.paInt16,
                channels=2,
                rate=44100,
                input=True,
                input_device_index=DEVICE_INDEX,
                frames_per_buffer=1024)

print("Listening to system audio... Press Ctrl+C to stop.")

try:
    while True:
        frames = []

        # Record for 5 seconds at a time
        for _ in range(0, int(44100 / 1024 * 5)):  # 5-second chunks
            data = stream.read(1024, exception_on_overflow=False)
            frames.append(data)

        # Save to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
            tmp_filename = tmpfile.name
            wf = wave.open(tmp_filename, 'wb')
            wf.setnchannels(2)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(44100)
            wf.writeframes(b''.join(frames))
            wf.close()

        # Transcribe with Whisper
        result = model.transcribe(tmp_filename)
        print("Transcription:", result["text"])

        # Remove temp file
        os.remove(tmp_filename)

except KeyboardInterrupt:
    print("\nStopping transcription...")

finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
