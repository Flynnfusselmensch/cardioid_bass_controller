"""
audio_engine.py

Bindeglied zwischen dem reinen DSP-Kern (dsp_core.py) und der Audio-Hardware
via sounddevice. Diese Schicht ist bewusst duenn gehalten: sie ruft nur
CardioidProcessor.process_block() im Audio-Callback auf. Wenn du spaeter auf
einen echten DSP portierst, ist genau diese Datei die, die komplett ersetzt
wird (durch den Audio-Interrupt-Handler des Zielsystems) - dsp_core.py bleibt
unveraendert wiederverwendbar.

Benoetigt: pip install sounddevice numpy
"""

import numpy as np
import sounddevice as sd  # Bibliothek fuer Audio-Ein-/Ausgabe (PortAudio-Wrapper)

from dsp_core import CardioidProcessor, SineOscillator


class AudioEngine:
    def __init__(self, processor: CardioidProcessor, oscillator: SineOscillator,
                 fs: int = 44100, blocksize: int = 256, device=None):
        self.processor = processor    # der DSP-Kern von dsp_core.py
        self.oscillator = oscillator  # der Testton-Generator
        self.fs = fs                  # Samplerate, muss zu dsp_core passen
        self.blocksize = blocksize    # wie viele Samples pro Callback-Aufruf
                                       # verarbeitet werden (kleiner = weniger
                                       # Latenz, aber mehr CPU-Overhead)
        self.device = device          # welches Audiogeraet genutzt wird
                                       # (None = Standardgeraet des Systems)
        self._stream = None           # haelt den aktiven sounddevice-Stream,
                                       # solange None ist nichts gestartet

    def _callback(self, outdata, frames, time_info, status):
        # Diese Funktion ruft sounddevice automatisch im Hintergrund auf,
        # sobald neue Audiodaten gebraucht werden (typischerweise alle paar
        # Millisekunden, je nach blocksize) - das ist der "Audio-Interrupt"
        # in Software-Form.
        if status:
            # z.B. Warnung bei Buffer-Unterlauf (Aussetzer) - nur zur Info
            print("AudioEngine status:", status)

        # 'frames' Samples vom Testton-Oszillator holen (ein kompletter Block)
        block = [self.oscillator.process_sample() for _ in range(frames)]

        # den kompletten Block durch die Cardioid-Verarbeitung schicken -
        # das ist der einzige Aufruf, der die eigentliche DSP-Arbeit macht
        out_a, out_b = self.processor.process_block(block)

        # Ergebnis in die beiden Ausgabekanaele schreiben:
        # Kanal 0 = links = Box A, Kanal 1 = rechts = Box B
        outdata[:, 0] = np.asarray(out_a, dtype=np.float32)
        outdata[:, 1] = np.asarray(out_b, dtype=np.float32)

    def start(self) -> None:
        if self._stream is not None:
            return  # laeuft schon, nichts zu tun (verhindert doppeltes Starten)
        self._stream = sd.OutputStream(
            samplerate=self.fs,
            channels=2,               # stereo: Kanal 0 = Box A, Kanal 1 = Box B
            dtype="float32",
            blocksize=self.blocksize,
            callback=self._callback,  # wird automatisch periodisch aufgerufen
            device=self.device,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def is_running(self) -> bool:
        return self._stream is not None

    @staticmethod
    def list_devices():
        # Hilfsfunktion: zeigt alle verfuegbaren Audiogeraete an (z.B. um
        # herauszufinden, welches 'device'-Argument man an __init__ geben muss)
        return sd.query_devices()