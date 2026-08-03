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

import math  # nur fuer pi, tan, sin - keine schweren Abhaengigkeiten


class OnePoleAllpass:
    """
    Digitaler Allpass 1. Ordnung. (Aktuell nur fuer Experimente genutzt,
    siehe CardioidProcessor.use_allpass - im Normalbetrieb NICHT aktiv,
    weil reine Verzoegerung die frequenzunabhaengige, korrekte Loesung ist.)

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
        self.fs = fs        # Samplerate in Hz, z.B. 44100 - wird fuer die
                             # Koeffizientenformel gebraucht (fc relativ zu fs)
        self.a = 0.0         # der eine Allpass-Koeffizient, bestimmt die
                             # gesamte Phasenkurve; 0.0 = neutral (keine Wirkung)
        self._x1 = 0.0        # Zustand: voriger Eingangswert x[n-1]
        self._y1 = 0.0        # Zustand: voriger Ausgangswert y[n-1]
                             # (beide zusammen = "Speicher" des Filters,
                             # das ist alles, was ein 1st-order-Filter braucht)

    def set_frequency(self, fc_hz: float) -> None:
        # theta = normierte Kreisfrequenz der Zielfrequenz fc, bezogen auf
        # die Samplerate. Bei fc=fs/2 (Nyquist) waere theta=pi/2.
        theta = math.pi * fc_hz / self.fs

        # tan(theta): kommt aus der "Bilinear-Transformation", dem Standard-
        # verfahren, um eine analoge RC-Schaltung (wie im Buch, Seite 409)
        # in eine digitale Differenzengleichung zu uebersetzen.
        t = math.tan(theta)

        # a bestimmt, WO (bei welcher Frequenz) die Phase genau -90 Grad
        # betraegt. Bei t=1 (also fc=fs/4) waere a=0 (neutral). Je weiter
        # fc von fs/4 entfernt ist, desto staerker weicht a von 0 ab.
        self.a = (t - 1.0) / (t + 1.0)

    def process_sample(self, x: float) -> float:
        # Die eigentliche Filter-Gleichung, ein einzelner Sample-Schritt:
        # neuer Ausgang = a*aktueller Eingang + voriger Eingang
        #                 - a*voriger Ausgang
        y = self.a * x + self._x1 - self.a * self._y1

        # Zustand fuer den naechsten Aufruf weiterschieben (x wird zu x[n-1],
        # y wird zu y[n-1]) - das "Gedaechtnis" des Filters aktualisieren
        self._x1 = x
        self._y1 = y
        return y

    def reset(self) -> None:
        # Zustand loeschen (z.B. vor einem neuen Testlauf), damit alte
        # Werte aus vorherigen Berechnungen nicht nachwirken
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
        # Puffergroesse in Samples: wie viele Samples passen maximal
        # in die laengste jemals gewuenschte Verzoegerung (50ms Standard,
        # +1 als Sicherheitsmarge)
        self._max_samples = int(fs * max_delay_ms / 1000.0) + 1
        # der eigentliche Speicher - ein Ringpuffer (Array), das zyklisch
        # ueberschrieben wird, statt staendig neuen Speicher anzufordern
        self._buffer = [0.0] * self._max_samples
        self._write_idx = 0     # wo als naechstes reingeschrieben wird
        self.delay_samples = 0  # wie viele Samples Verzoegerung aktuell aktiv sind

    def set_delay_ms(self, delay_ms: float) -> None:
        # Millisekunden in eine ganze Anzahl Samples umrechnen (die
        # Verzoegerung kann nur in ganzen Samples ausgedrueckt werden -
        # das ist die Quelle der kleinen Rundungsabweichung, die wir
        # vorhin gemessen hatten: 2,915ms Ideal vs. 2,925ms real)
        samples = int(round(delay_ms / 1000.0 * self.fs))
        # innerhalb der erlaubten Pufferrgroesse begrenzen (nie negativ,
        # nie groesser als der reservierte Speicher)
        self.delay_samples = max(0, min(samples, self._max_samples - 1))

    def process_sample(self, x: float) -> float:
        # neuen Wert an der aktuellen Schreibposition ablegen
        self._buffer[self._write_idx] = x

        # Leseposition = Schreibposition MINUS die gewuenschte Verzoegerung
        # (im Kreis "zurueckgerechnet", daher der Modulo %) - genau DAS ist
        # die eigentliche Verzoegerung: wir lesen einen aelteren Wert,
        # der vor 'delay_samples' Schritten geschrieben wurde
        read_idx = (self._write_idx - self.delay_samples) % self._max_samples
        y = self._buffer[read_idx]

        # Schreibposition fuer den naechsten Sample-Schritt weiterbewegen
        # (wieder zyklisch, daher %)
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
        self._phase = 0.0              # aktuelle Position auf der Sinuskurve (0 bis 2*pi)
        self._two_pi = 2.0 * math.pi   # einmal berechnet, spart Rechenzeit im Audio-Pfad

    def set_frequency(self, freq_hz: float) -> None:
        self.freq_hz = freq_hz

    def process_sample(self) -> float:
        # aktuellen Sinuswert an der jetzigen Phasenposition auslesen
        val = math.sin(self._phase)

        # Phase fuer den naechsten Sample weiterdrehen: wie weit sich die
        # Phase pro Sample aendert, haengt direkt von freq_hz/fs ab -
        # hoehere Frequenz = groesserer Sprung pro Sample
        self._phase += self._two_pi * self.freq_hz / self.fs

        # Phase im Bereich 0..2*pi halten (verhindert, dass die Zahl
        # nach langer Laufzeit unbegrenzt waechst und ungenau wird)
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

    SPEED_OF_SOUND_M_S = 343.0  # m/s, Standardwert bei ca. 20 Grad Celsius

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
        self.delay = DelayLine(fs)      # die eigentliche, breitbandig wirkende Komponente
        self.allpass = OnePoleAllpass(fs)  # nur fuer Experimente (siehe oben)
        self.invert = invert            # die Polaritaetsumkehr - erzeugt erst die
                                         # Cardioid-Form statt einer Dipol-/Achterform
        self.use_allpass = use_allpass

    def set_frequency(self, fc_hz: float) -> None:
        # betrifft NUR den (im Normalbetrieb ungenutzten) Allpass - hat
        # keinen Einfluss auf delay_samples/die eigentliche Ausloeschung
        self.allpass.set_frequency(fc_hz)

    def set_distance_m(self, distance_m: float) -> None:
        # Kernrechnung: physischer Abstand in Sekunden umrechnen, dann als
        # Millisekunden an die DelayLine weitergeben. Das ist die einzige
        # Stelle, die fuer die eigentliche Auslöschung wirklich zaehlt.
        delay_ms = distance_m / self.SPEED_OF_SOUND_M_S * 1000.0
        self.delay.set_delay_ms(delay_ms)

    def process_sample(self, x: float):
        box_a = x  # Box A bekommt das Signal 1:1, unveraendert

        y = self.delay.process_sample(x)  # Box B: zuerst um d/c verzoegern

        if self.use_allpass:
            # nur im Experimentiermodus zusaetzlich Phase drehen -
            # im Normalbetrieb (False) wird dieser Block uebersprungen
            y = self.allpass.process_sample(y)

        # Polaritaet umkehren (das eigentliche Herzstueck der Cardioid-
        # Erzeugung, siehe Polardiagramm-Herleitung: ohne diese Zeile
        # entsteht nur eine Achterform, keine Cardioidform)
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