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
import sounddevice as sd

from dsp_core import CardioidProcessor, SineOscillator


class AudioEngine:
    def __init__(self, processor: CardioidProcessor, oscillator: SineOscillator,
                 fs: int = 44100, blocksize: int = 256, device=None):
        self.processor = processor
        self.oscillator = oscillator
        self.fs = fs
        self.blocksize = blocksize
        self.device = device
        self._stream = None

    def _callback(self, outdata, frames, time_info, status):
        if status:
            print("AudioEngine status:", status)
        block = [self.oscillator.process_sample() for _ in range(frames)]
        out_a, out_b = self.processor.process_block(block)
        outdata[:, 0] = np.asarray(out_a, dtype=np.float32)
        outdata[:, 1] = np.asarray(out_b, dtype=np.float32)

    def start(self) -> None:
        if self._stream is not None:
            return
        self._stream = sd.OutputStream(
            samplerate=self.fs,
            channels=2,
            dtype="float32",
            blocksize=self.blocksize,
            callback=self._callback,
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
        return sd.query_devices()

print("audio engine is running")