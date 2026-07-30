# Cardioid Bass Cabinet Controller

Python-GUI zum Live-Abstimmen eines Cardioid-Bass-Setups: EIN Frequenzregler
steuert Testton **und** Allpass-Phasendrehung gleichzeitig, EIN Abstandsregler
steuert die Delay-Zeit zwischen den beiden Boxen.

## Installation

```bash
pip install numpy sounddevice
```

Unter Linux ggf. zusaetzlich:

```bash
sudo apt install python3-tk portaudio19-dev
```

(Windows/Mac: tkinter ist im Standard-Python-Installer bereits enthalten.)

## Start

```bash
python3 main.py
```

Es oeffnet sich ein Fenster mit zwei Reglern (Frequenz, Abstand) und
Start/Stop-Buttons. Kanal 1 des Audio-Ausgangs = unbearbeiteter Testton
(Box A), Kanal 2 = verzoegert + phasengedreht + invertiert (Box B).

## Aufbau der Dateien

| Datei | Zweck |
|---|---|
| `dsp_core.py` | Reine DSP-Logik (Allpass, Delay-Line, Oszillator, CardioidProcessor). Keine Audio-Library-Abhaengigkeit, sample-fuer-sample-Struktur, gedacht fuer spaetere Portierung auf einen DSP-Chip. |
| `audio_engine.py` | Bindet `dsp_core` an `sounddevice` (Echtzeit-Audio-I/O). |
| `gui.py` | Tkinter-Oberflaeche, ruft nur die `set_*()`-Methoden des Prozessors auf. |
| `main.py` | Verdrahtet alles zusammen, Startpunkt. |

## Fuer eine spaetere DSP-Portierung

`dsp_core.py` ist absichtlich so geschrieben, dass sie sich fast 1:1 in C/C++
uebertragen laesst:

- Explizite Zustandsvariablen statt Numpy-Vektoroperationen (`_x1`, `_y1` bei
  `OnePoleAllpass`, Ringpuffer bei `DelayLine`).
- Koeffizientenberechnung (`set_frequency`, `set_distance_m`) laeuft nur bei
  Parameteraenderung, NICHT im Audio-Callback - genau wie man es auf einem
  DSP trennen wuerde (Control-Rate vs. Audio-Rate).
- `process_sample()` enthaelt nur die minimalen Multiply-Add-Operationen, die
  auch im Audio-Interrupt eines echten DSP laufen wuerden.

Wenn der Schritt ansteht, portiere einfach `dsp_core.py` Klasse fuer Klasse
nach C - Variablennamen und Struktur bleiben identisch.
