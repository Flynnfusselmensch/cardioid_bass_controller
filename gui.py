"""
gui.py

Tkinter-Oberflaeche. Reine Steuerungsebene - fasst den DSP-Kern nie direkt an,
ausser ueber dessen oeffentliche set_*()-Methoden (control-rate, nicht
audio-rate). Bewusst von der Audio-Engine getrennt, damit du die GUI komplett
austauschen (z.B. gegen ein Web-Interface oder Hardware-Poti-Eingaben) kannst,
ohne dsp_core.py oder audio_engine.py anzufassen.
"""

import tkinter as tk
from tkinter import ttk

from dsp_core import CardioidProcessor, SineOscillator
from audio_engine import AudioEngine


class CardioidGUI:
    def __init__(self, processor: CardioidProcessor, oscillator: SineOscillator,
                 engine: AudioEngine):
        self.processor = processor
        self.oscillator = oscillator
        self.engine = engine

        self.root = tk.Tk()
        self.root.title("Cardioid Bass Cabinet Controller")
        self.root.geometry("420x320")
        # sorgt dafuer, dass beim Fensterschliessen auch die Audio-Engine
        # sauber gestoppt wird (statt dass der Stream im Hintergrund haengt)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_widgets()
        # einmalig direkt beim Start die aktuellen Werte anwenden, damit
        # Anzeige/Berechnung schon vor dem ersten Reglerbewegen stimmen
        self._on_freq_change(self.oscillator.freq_hz)
        self._on_dist_change(1.0)

    def _build_widgets(self):
        pad = {"padx": 12, "pady": 6}  # gemeinsamer Randabstand fuer alle Widgets

        # --- Frequenzregler ---
        ttk.Label(self.root, text="Frequenz (Hz)", font=("Arial", 11, "bold")).pack(**pad)
        self.freq_var = tk.DoubleVar(value=self.oscillator.freq_hz)  # haelt den aktuellen Wert
        self.freq_scale = ttk.Scale(
            self.root, from_=20, to=500, orient=tk.HORIZONTAL,
            variable=self.freq_var,
            command=self._on_freq_change,  # wird bei jeder Reglerbewegung aufgerufen
            length=350,
        )
        self.freq_scale.pack(**pad)
        self.freq_label = ttk.Label(self.root, text="")  # zeigt den Zahlenwert als Text an
        self.freq_label.pack()

        # --- Abstandsregler ---
        ttk.Label(self.root, text="Boxenabstand (m)", font=("Arial", 11, "bold")).pack(**pad)
        self.dist_var = tk.DoubleVar(value=1.0)
        self.dist_scale = ttk.Scale(
            self.root, from_=0.0, to=3.0, orient=tk.HORIZONTAL,
            variable=self.dist_var, command=self._on_dist_change, length=350,
        )
        self.dist_scale.pack(**pad)
        self.dist_label = ttk.Label(self.root, text="")
        self.dist_label.pack()

        # --- Info-Zeile: zeigt live die berechneten internen Werte ---
        self.info_label = ttk.Label(self.root, text="", foreground="gray20")
        self.info_label.pack(pady=10)

        # --- Start/Stop-Buttons ---
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10)
        self.start_btn = ttk.Button(btn_frame, text="Start", command=self._start)
        self.start_btn.grid(row=0, column=0, padx=6)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self._stop, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=6)

        self.status_label = ttk.Label(self.root, text="Gestoppt", foreground="firebrick")
        self.status_label.pack()

        # --- Experimentier-Checkbox fuer den (im Normalbetrieb ausgeschalteten) Allpass ---
        self.allpass_var = tk.BooleanVar(value=self.processor.use_allpass)
        allpass_check = ttk.Checkbutton(
            self.root, text="Zusaetzlicher Allpass (nur Experimente - verschlechtert breitbandige Ausloeschung)",
            variable=self.allpass_var, command=self._on_allpass_toggle,
        )
        allpass_check.pack(pady=(15, 0))
        ttk.Label(
            self.root,
            text="Standard: AUS. Reines Delay+Invert aus dem Abstand loescht bei\nallen Frequenzen aus - kein Frequenzabgleich noetig.",
            foreground="gray40", justify=tk.CENTER,
        ).pack()

    def _on_freq_change(self, _value):
        # _value kommt automatisch von ttk.Scale, wir lesen den Wert aber
        # lieber direkt aus freq_var (gleiches Ergebnis, etwas robuster)
        f = float(self.freq_var.get())
        self.oscillator.set_frequency(f)   # bestimmt die Tonhoehe des Testtons
        self.processor.set_frequency(f)    # betrifft NUR den (meist inaktiven) Allpass
        self.freq_label.config(text=f"{f:.1f} Hz")
        self._update_info()

    def _on_dist_change(self, _value):
        d = float(self.dist_var.get())
        self.processor.set_distance_m(d)   # das ist die eigentlich wichtige Rechnung
                                            # (siehe dsp_core.py: d/c -> delay_ms)
        self.dist_label.config(text=f"{d:.2f} m")
        self._update_info()

    def _update_info(self):
        # Delay in Samples zurueck in Millisekunden umrechnen, nur zur Anzeige
        delay_ms = self.processor.delay.delay_samples / self.processor.fs * 1000.0
        self.info_label.config(
            text=f"Allpass-Koeffizient a = {self.processor.allpass.a:.4f}   |   "
                 f"Delay = {delay_ms:.2f} ms"
        )

    def _on_allpass_toggle(self):
        # Checkbox-Zustand direkt in den Prozessor uebernehmen
        self.processor.use_allpass = self.allpass_var.get()

    def _start(self):
        self.engine.start()  # startet den echten Audio-Stream (sounddevice)
        self.start_btn.config(state=tk.DISABLED)  # verhindert doppeltes Starten
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Laeuft", foreground="darkgreen")

    def _stop(self):
        self.engine.stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Gestoppt", foreground="firebrick")

    def _on_close(self):
        # sauber aufraeumen, bevor das Fenster tatsaechlich schliesst
        self.engine.stop()
        self.root.destroy()

    def run(self):
        # startet die Tkinter-Eventschleife - blockiert, bis das Fenster
        # geschlossen wird (alles danach in main.py wuerde erst dann laufen)
        self.root.mainloop()