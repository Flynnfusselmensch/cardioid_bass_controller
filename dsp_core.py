"""
dsp_core.py

Reine DSP-Logik, KEINE Audio-Library-Abhaengigkeit (kein sounddevice, kein numpy
im heissen Pfad). Absicht: dieser Code soll 1:1 lesbar/uebertragbar sein auf eine
spaetere Implementierung auf einem DSP-Chip (z.B. ARM Cortex-M + CMSIS-DSP,
SHARC, Blackfin) oder in C/C++.

Designprinzipien fuer die DSP-Portierbarkeit:
- Jede Klasse haelt ihren Zustand explizit als einfache Skalare/Listen (kein
  verstecktes Numpy-Broadcasting), genau wie ein Filter auf einem DSP das tun
  wuerde (Direct-Form-1-Struktur mit expliziten Zustandsvariablen).
- Koeffizienten-Berechnung (set_frequency, set_distance_m) laeuft nur bei
  Parameteraenderung (Steuerrate/Control-Rate) - NICHT im Audio-Callback.
  Der eigentliche process_sample()-Pfad enthaelt nur die minimalen
  Multiply-Add-Operationen, die auch auf einem DSP im Audio-Interrupt
  laufen wuerden.
- Delay-Line als Ringpuffer (Standardtechnik auf DSPs, kein dynamisches
  Speicher-Handling im Audio-Pfad).
"""

import math


class OnePoleAllpass:
    """
    Digitaler Allpass 1. Ordnung.

    Differenzengleichung (Zoelzer, DAFX):
        y[n] = a*x[n] + x[n-1] - a*y[n-1]

    Uebertragungsfunktion:
        H(z) = (a + z^-1) / (1 + a*z^-1)

    Eigenschaft: |H(e^jw)| = 1 fuer alle w (echter Allpass, keine
    Amplitudenaenderung). Bei der Koeffizienten-Frequenz fc betraegt die
    Phasendrehung exakt -90 Grad.

    a = (tan(pi*fc/fs) - 1) / (tan(pi*fc/fs) + 1)
    """

    def __init__(self, fs: float):
        self.fs = fs
        self.a = 0.0
        self._x1 = 0.0
        self._y1 = 0.0

    def set_frequency(self, fc_hz: float) -> None:
        theta = math.pi * fc_hz / self.fs
        t = math.tan(theta)
        self.a = (t - 1.0) / (t + 1.0)

    def process_sample(self, x: float) -> float:
        y = self.a * x + self._x1 - self.a * self._y1
        self._x1 = x
        self._y1 = y
        return y

    def reset(self) -> None:
        self._x1 = 0.0
        self._y1 = 0.0


class DelayLine:
    """
    Einfache Verzoegerungsleitung als Ringpuffer, Verzoegerungszeit in ms
    einstellbar. max_delay_ms definiert die Puffergroesse (einmalig beim
    Start reserviert, wie auf einem DSP mit statischem Speicher).
    """

    def __init__(self, fs: float, max_delay_ms: float = 50.0):
        self.fs = fs
        self._max_samples = int(fs * max_delay_ms / 1000.0) + 1
        self._buffer = [0.0] * self._max_samples
        self._write_idx = 0
        self.delay_samples = 0

    def set_delay_ms(self, delay_ms: float) -> None:
        samples = int(round(delay_ms / 1000.0 * self.fs))
        self.delay_samples = max(0, min(samples, self._max_samples - 1))

    def process_sample(self, x: float) -> float:
        self._buffer[self._write_idx] = x
        read_idx = (self._write_idx - self.delay_samples) % self._max_samples
        y = self._buffer[read_idx]
        self._write_idx = (self._write_idx + 1) % self._max_samples
        return y

    def reset(self) -> None:
        self._buffer = [0.0] * self._max_samples
        self._write_idx = 0


class SineOscillator:
    """Einfacher Testton-Generator (Phasenakkumulator, DSP-ueblich)."""

    def __init__(self, fs: float, freq_hz: float = 100.0):
        self.fs = fs
        self.freq_hz = freq_hz
        self._phase = 0.0
        self._two_pi = 2.0 * math.pi

    def set_frequency(self, freq_hz: float) -> None:
        self.freq_hz = freq_hz

    def process_sample(self) -> float:
        val = math.sin(self._phase)
        self._phase += self._two_pi * self.freq_hz / self.fs
        if self._phase >= self._two_pi:
            self._phase -= self._two_pi
        return val

    def reset(self) -> None:
        self._phase = 0.0


class CardioidProcessor:
    """
    Kombiniert DelayLine + OnePoleAllpass + Polaritaetsinvertierung zu einem
    Cardioid-Bass-Prozessor mit zwei Ausgaengen:
      - box_a: unbearbeitetes Signal
      - box_b: verzoegert (Boxenabstand) + phasengedreht (Zielfrequenz) +
               invertiert

    EIN Frequenzparameter (set_frequency) steuert den Allpass.
    EIN Abstandsparameter (set_distance_m) steuert die Delay-Line.
    Beide zusammen ergeben die Auslöschung nach hinten bei der Zielfrequenz.
    """

    SPEED_OF_SOUND_M_S = 343.0

    def __init__(self, fs: float, invert: bool = True, use_allpass: bool = False):
        """
        use_allpass=False (Standard): reine Delay+Invert-Ausloeschung, aus dem
        Boxenabstand berechnet. Das ist FREQUENZUNABHAENGIG (breitband) - der
        Zeitversatz d/c kompensiert den akustischen Laufwegsunterschied exakt,
        fuer jede Frequenz gleichermassen. Kein Frequenzparameter noetig.

        use_allpass=True: zusaetzlich ein Allpass, der NUR bei der eingestellten
        fc exakt passt. Ausserhalb von fc verschlechtert sich die Ausloeschung
        wieder (siehe Herleitung/Messung) - nur sinnvoll fuer Experimente mit
        Einzelfrequenz-Feintuning, NICHT fuer normalen Betrieb.
        """
        self.fs = fs
        self.delay = DelayLine(fs)
        self.allpass = OnePoleAllpass(fs)
        self.invert = invert
        self.use_allpass = use_allpass

    def set_frequency(self, fc_hz: float) -> None:
        self.allpass.set_frequency(fc_hz)

    def set_distance_m(self, distance_m: float) -> None:
        delay_ms = distance_m / self.SPEED_OF_SOUND_M_S * 1000.0
        self.delay.set_delay_ms(delay_ms)

    def process_sample(self, x: float):
        box_a = x
        y = self.delay.process_sample(x)
        if self.use_allpass:
            y = self.allpass.process_sample(y)
        box_b = -y if self.invert else y
        return box_a, box_b

    def process_block(self, block):
        """block: Liste/iterable von floats (ein Kanal, ein Audio-Block)."""
        out_a = [0.0] * len(block)
        out_b = [0.0] * len(block)
        for i, x in enumerate(block):
            a, b = self.process_sample(x)
            out_a[i] = a
            out_b[i] = b
        return out_a, out_b

    def reset(self) -> None:
        self.delay.reset()
        self.allpass.reset()