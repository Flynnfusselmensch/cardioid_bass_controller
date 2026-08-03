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

FS = 44100        # Samplerate - muss ueberall identisch verwendet werden,
                   # sonst stimmen Frequenz-/Delay-Berechnungen nicht mehr
BLOCKSIZE = 256    # Groesse der Audio-Bloecke (siehe audio_engine.py)


def main():
    # Reihenfolge wichtig: erst die DSP-Bausteine erzeugen ...
    processor = CardioidProcessor(FS, invert=True)
    oscillator = SineOscillator(FS, freq_hz=100.0)

    # ... dann die Audio-Engine, die beide zusammen antreibt ...
    engine = AudioEngine(processor, oscillator, fs=FS, blocksize=BLOCKSIZE)

    # ... und zuletzt die GUI, die auf alle drei Objekte zugreift
    gui = CardioidGUI(processor, oscillator, engine)
    gui.run()  # blockiert hier, bis das Fenster geschlossen wird


if __name__ == "__main__":
    main()