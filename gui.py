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
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_widgets()
        self._on_freq_change(self.oscillator.freq_hz)
        self._on_dist_change(1.0)

    def _build_widgets(self):
        pad = {"padx": 12, "pady": 6}

        ttk.Label(self.root, text="Frequenz (Hz)", font=("Arial", 11, "bold")).pack(**pad)
        self.freq_var = tk.DoubleVar(value=self.oscillator.freq_hz)
        self.freq_scale = ttk.Scale(
            self.root, from_=20, to=500, orient=tk.HORIZONTAL,
            variable=self.freq_var, command=self._on_freq_change, length=350,
        )
        self.freq_scale.pack(**pad)
        self.freq_label = ttk.Label(self.root, text="")
        self.freq_label.pack()

        ttk.Label(self.root, text="Boxenabstand (m)", font=("Arial", 11, "bold")).pack(**pad)
        self.dist_var = tk.DoubleVar(value=1.0)
        self.dist_scale = ttk.Scale(
            self.root, from_=0.0, to=3.0, orient=tk.HORIZONTAL,
            variable=self.dist_var, command=self._on_dist_change, length=350,
        )
        self.dist_scale.pack(**pad)
        self.dist_label = ttk.Label(self.root, text="")
        self.dist_label.pack()

        self.info_label = ttk.Label(self.root, text="", foreground="gray20")
        self.info_label.pack(pady=10)

        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10)
        self.start_btn = ttk.Button(btn_frame, text="Start", command=self._start)
        self.start_btn.grid(row=0, column=0, padx=6)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self._stop, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=6)

        self.status_label = ttk.Label(self.root, text="Gestoppt", foreground="firebrick")
        self.status_label.pack()

    def _on_freq_change(self, _value):
        f = float(self.freq_var.get())
        self.oscillator.set_frequency(f)
        self.processor.set_frequency(f)
        self.freq_label.config(text=f"{f:.1f} Hz")
        self._update_info()

    def _on_dist_change(self, _value):
        d = float(self.dist_var.get())
        self.processor.set_distance_m(d)
        self.dist_label.config(text=f"{d:.2f} m")
        self._update_info()

    def _update_info(self):
        delay_ms = self.processor.delay.delay_samples / self.processor.fs * 1000.0
        self.info_label.config(
            text=f"Allpass-Koeffizient a = {self.processor.allpass.a:.4f}   |   "
                 f"Delay = {delay_ms:.2f} ms"
        )

    def _start(self):
        self.engine.start()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Laeuft", foreground="darkgreen")

    def _stop(self):
        self.engine.stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Gestoppt", foreground="firebrick")

    def _on_close(self):
        self.engine.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
