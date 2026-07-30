"""
main.py

Startpunkt. Baut die drei Schichten zusammen:
  dsp_core.CardioidProcessor / SineOscillator   (portierbare DSP-Logik)
  audio_engine.AudioEngine                      (sounddevice I/O)
  gui.CardioidGUI                                (Tkinter-Steuerung)
"""

from dsp_core import CardioidProcessor, SineOscillator
from audio_engine import AudioEngine
from gui import CardioidGUI

FS = 44100
BLOCKSIZE = 256


def main():
    processor = CardioidProcessor(FS, invert=True)
    oscillator = SineOscillator(FS, freq_hz=100.0)
    engine = AudioEngine(processor, oscillator, fs=FS, blocksize=BLOCKSIZE)

    gui = CardioidGUI(processor, oscillator, engine)
    gui.run()

print("hello world")

if __name__ == "__main__":
    main()


