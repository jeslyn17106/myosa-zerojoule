import dash
from dash import dcc, html
from dash.dependencies import Output, Input
import plotly.graph_objs as go
import serial
import threading
import time
from collections import deque

# --- SERIAL CONFIGURATION ---
SERIAL_PORT = 'COM3'  # Update to your ESP32 COM port
BAUD_RATE = 115200

# Data Buffers
MAX_POINTS = 50
buffer_lock = threading.Lock()
time_buffer = deque(maxlen=MAX_POINTS)
vibe_buffer = deque(maxlen=MAX_POINTS)
attack_buffer = deque(maxlen=MAX_POINTS)
dampening_buffer = deque(maxlen=MAX_POINTS)

current_status = {"class": "NORMAL", "action": "SYSTEM SAFE", "active": False, "seis": 0.0}
attack_labels = {0: "NORMAL", 25: "RESONANCE ATTACK", 50: "SWEEP ATTACK", 75: "BURST ATTACK"}

# --- SERIAL THREAD ---
def read_serial():
    global current_status
    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
            print(f"Connected to ESP32 on {SERIAL_PORT}")
        except Exception as e:
            print(f"Serial Error (connect): {e} — retrying in 3s")
            time.sleep(3)
            continue

        try:
            while True:
                if ser.in_waiting > 0:
                    raw = ser.readline()
                    line = raw.decode('utf-8', errors='ignore').strip()
                    if not line or "Attack_Class" not in line:
                        continue

                    try:
                        parts = line.split(',')
                        data = {}
                        for p in parts:
                            if ':' not in p:
                                raise ValueError(f"malformed field: {p!r}")
                            k, v = p.split(':', 1)
                            data[k.strip()] = float(v.strip())

                        now = time.strftime('%H:%M:%S')
                        attack_val = int(data.get('Attack_Class', 0))
                        damp_val = int(data.get('Dampening_Active', 0))
                        vibe_val = data.get('Vibe_Amplitude', 0.0)
                        seis_val = data.get('SEIS', 0.0)

                        with buffer_lock:
                            time_buffer.append(now)
                            attack_buffer.append(attack_val)
                            dampening_buffer.append(damp_val)
                            vibe_buffer.append(vibe_val)

                        attack_name = attack_labels.get(attack_val, "UNKNOWN")
                        damp_active = damp_val > 0

                        action_text = "ACTIVE MONITORING"
                        if attack_val == 25: action_text = "FREQUENCY SHIFT (PWM 140)"
                        elif attack_val == 50: action_text = "SAFE SPEED LOCK (PWM 120)"
                        elif attack_val == 75: action_text = "EMERGENCY POWER CUT (PWM 0)"

                        current_status = {
                            "class": attack_name,
                            "action": action_text if damp_active else "ACTIVE MONITORING",
                            "active": damp_active,
                            "seis": seis_val
                        }
                    except Exception as parse_err:
                        print(f"Skipped malformed line ({parse_err}): {line!r}")
                        continue
        except (serial.SerialException, OSError) as conn_err:
            print(f"Serial Error (connection lost): {conn_err} — reconnecting...")
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(2)
            continue

threading.Thread(target=read_serial, daemon=True).start()

# --- DASH APP ---
app = dash.Dash(
    __name__,
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Newsreader:ital,wght@0,600;0,700;1,600&display=swap"
    ],
    suppress_callback_exceptions=True
)

app.index_string = '''
<!DOCTYPE html>
<html>
<head>
{%metas%}
<title>ZeroJoule — Physics-Layer IoT Defense</title>
{%favicon%}
{%css%}
<style>
  *, *::before, *::after { box-sizing: border-box; }
  html, body { background: #F6F4EE; -webkit-font-smoothing: antialiased; }

  /* Tab overrides — cream/editorial theme */
  .tab--selected { border-bottom: 2px solid #161513 !important; color: #161513 !important; background: transparent !important; }
  .tab { border: none !important; border-bottom: 1px solid #DEDACD !important; background: transparent !important; color: #95907F !important; font-family: 'JetBrains Mono', monospace !important; font-size: 11px !important; letter-spacing: 0.12em !important; font-weight: 500 !important; padding: 14px 26px !important; text-transform: uppercase !important; }
  .tabs { border-bottom: none !important; }

  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: #F6F4EE; }
  ::-webkit-scrollbar-thumb { background: rgba(22,21,19,0.2); border-radius: 3px; }
</style>
</head>
<body>
{%app_entry%}
<footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>
'''

# --- COLOR / FONT SCHEME ---
MONO_FONT = "'JetBrains Mono', monospace"
SERIF_FONT = "'Newsreader', serif"

BG = '#F6F4EE'           
WHITE_PANEL = '#FFFFFF'  
BORDER = '#DEDACD'       
TEXT_MAIN = '#161513'    
TEXT_MUTED = '#95907F'   

ACCENT_RED = '#B3413A'
ACCENT_GREEN = '#3F7A5E'
ACCENT_AMBER = '#B4823A'

LABEL_STYLE = {
    'margin': '0', 'fontSize': '11px', 'color': TEXT_MUTED, 'fontWeight': '500',
    'fontFamily': MONO_FONT, 'letterSpacing': '1.5px', 'textTransform': 'uppercase'
}


# --- REUSABLE COMPONENTS ---

def eyebrow(text):
    return html.Div(f"—— {text}", style={
        'fontSize': '11px', 'color': TEXT_MUTED, 'fontFamily': MONO_FONT,
        'letterSpacing': '1.5px', 'marginBottom': '16px', 'textTransform': 'uppercase'
    })

def headline(text, size='30px'):
    return html.H2(text, style={
        'margin': '0 0 16px 0', 'fontSize': size, 'fontWeight': '700',
        'fontFamily': SERIF_FONT, 'fontStyle': 'italic', 'color': TEXT_MAIN, 'lineHeight': '1.2'
    })

def body_text(text, extra_style=None):
    style = {
        'fontSize': '13px', 'color': TEXT_MAIN, 'fontFamily': MONO_FONT,
        'lineHeight': '1.65', 'margin': '0'
    }
    if extra_style:
        style.update(extra_style)
    return html.P(text, style=style)

def hr_line(margin='24px 0'):
    return html.Hr(style={'border': 'none', 'borderTop': f'1px solid {BORDER}', 'margin': margin})

def mono_tag(text, color=ACCENT_AMBER):
    return html.Span(text, style={
        'fontFamily': MONO_FONT, 'fontSize': '10px', 'letterSpacing': '0.06em',
        'color': color, 'background': f'{color}1A', 'padding': '3px 8px',
        'borderRadius': '3px', 'fontWeight': '500', 'textTransform': 'uppercase'
    })

def section_header(title, subtitle=None):
    children = [headline(title, size='30px')]
    if subtitle:
        children.append(body_text(subtitle, {'color': TEXT_MUTED, 'paddingBottom': '6px'}))
    return html.Div(style={
        'display': 'grid', 'gridTemplateColumns': '380px 1fr' if subtitle else '1fr', 'gap': '56px',
        'marginBottom': '48px', 'alignItems': 'end', 'padding': '30px 40px 0 40px'
    }, children=children)

def table_header(cols):
    return html.Div(style={
        'display': 'grid', 'gridTemplateColumns': cols['template'], 'gap': '32px',
        'padding': '36px 40px 14px 40px', 'borderBottom': f'2px solid {TEXT_MAIN}',
        'margin': '0 0 0 0'
    }, children=[
        html.Div(c, style={
            'fontFamily': MONO_FONT, 'fontSize': '10px', 'letterSpacing': '0.1em',
            'color': TEXT_MUTED, 'textTransform': 'uppercase'
        }) for c in cols['labels']
    ])


# ══════════════════════════════════════════════
# TAB 1 — LIVE MONITOR
# ══════════════════════════════════════════════
def live_tab_content():
    return html.Div([

        # Alert Banner
        html.Div(id='alert-banner', style={
            'padding': '18px 40px', 'borderBottom': f'1px solid {BORDER}'
        }),

        # 3 Metric Cards
        html.Div(style={
            'display': 'grid', 'gridTemplateColumns': 'repeat(3, 1fr)',
            'borderBottom': f'1px solid {BORDER}'
        }, children=[
            html.Div(style={'padding': '26px 40px', 'borderRight': f'1px solid {BORDER}'}, children=[
                html.P("THREAT CLASS", style=LABEL_STYLE),
                html.H3(id='card-threat', style={
                    'margin': '14px 0 6px 0', 'fontSize': '22px', 'fontWeight': '700', 'fontFamily': MONO_FONT
                }),
                html.P("Live from edge classifier", style={
                    'margin': '0', 'fontSize': '12px', 'color': TEXT_MUTED, 'fontFamily': MONO_FONT
                })
            ]),
            html.Div(style={'padding': '26px 40px', 'borderRight': f'1px solid {BORDER}'}, children=[
                html.P("COUNTERMEASURE", style=LABEL_STYLE),
                html.H3(id='card-action', style={
                    'margin': '14px 0 6px 0', 'fontSize': '18px', 'fontWeight': '700', 'fontFamily': MONO_FONT,
                    'color': ACCENT_AMBER
                }),
                html.P("Adaptive PWM dampening", style={
                    'margin': '0', 'fontSize': '12px', 'color': TEXT_MUTED, 'fontFamily': MONO_FONT
                })
            ]),
            html.Div(style={'padding': '26px 40px'}, children=[
                html.P("VIBRATION AMPLITUDE", style=LABEL_STYLE),
                html.H3(id='card-vibe', style={
                    'margin': '14px 0 6px 0', 'fontSize': '22px', 'fontWeight': '700', 'fontFamily': MONO_FONT
                }),
                html.P("MPU6050 accelerometer", style={
                    'margin': '0', 'fontSize': '12px', 'color': TEXT_MUTED, 'fontFamily': MONO_FONT
                })
            ])
        ]),

        # Graph + SEIS panel
        html.Div(style={
            'display': 'grid', 'gridTemplateColumns': '2fr 1fr', 'gap': '0'
        }, children=[

            # Telemetry graph
            html.Div(style={'padding': '30px 40px', 'borderRight': f'1px solid {BORDER}'}, children=[
                html.Div(" REAL-TIME TELEMETRY · MPU6050 AT 200HZ", style={
                    'fontSize': '11px', 'color': TEXT_MUTED, 'fontFamily': MONO_FONT,
                    'letterSpacing': '1.5px', 'marginBottom': '16px', 'textTransform': 'uppercase'
                }),
                html.Div(style={'backgroundColor': WHITE_PANEL, 'border': f'1px solid {BORDER}'}, children=[
                    dcc.Graph(id='live-graph', config={'displayModeBar': False})
                ])
            ]),

            # SEIS panel
            html.Div(style={'padding': '30px 40px'}, children=[
                html.Div("—— SECURITY-ENERGY IMPACT", style={
                    'fontSize': '11px', 'color': TEXT_MUTED, 'fontFamily': MONO_FONT,
                    'letterSpacing': '1.5px', 'marginBottom': '16px', 'textTransform': 'uppercase'
                }),
                html.H2("SEIS Total Energy", style={
                    'margin': '0 0 18px 0', 'fontSize': '26px', 'fontWeight': '700',
                    'fontFamily': SERIF_FONT, 'fontStyle': 'italic', 'color': TEXT_MAIN
                }),
                html.Div(id='card-seis', style={
                    'fontSize': '30px', 'fontWeight': '700', 'fontFamily': MONO_FONT, 'marginBottom': '6px'
                }),
                html.P("JOULES WASTED BY ATTACK", style={
                    'margin': '0 0 22px 0', 'fontSize': '11px', 'color': TEXT_MUTED,
                    'fontFamily': MONO_FONT, 'letterSpacing': '1.5px'
                }),
                html.P(
                    "SEIS quantifies the physical energy cost of each attack — integrating the "
                    "excess power draw against the normal baseline, reported in Joules.",
                    style={
                        'fontSize': '13px', 'color': TEXT_MAIN, 'fontFamily': MONO_FONT,
                        'lineHeight': '1.6', 'marginBottom': '20px'
                    }
                ),
                html.Div("SEIS = ∫₀ᵀ [P_attack(t) - P_normal(t)] dt", style={
                    'backgroundColor': WHITE_PANEL, 'border': f'1px solid {BORDER}', 'padding': '14px 16px',
                    'fontFamily': MONO_FONT, 'fontSize': '13px', 'color': TEXT_MAIN
                })
            ])
        ]),
    ])


# ══════════════════════════════════════════════
# TAB 2 — PIPELINE
# ══════════════════════════════════════════════
def pipeline_tab():
    layers = [
        {'num': '01', 'name': 'Kalman Filter', 'role': 'Signal isolation',
         'desc': 'State estimation filter running on ESP32 Core 0 at 200Hz. Separates true mechanical vibration from sensor noise and electrical interference. Outputs the residual r(k) — the deviation from expected normal operation.',
         'output': 'Residual signal r(k)', 'math': 'r(k) = z(k) − Hx̂(k|k−1)'},
        {'num': '02', 'name': 'FFT Analysis', 'role': 'Resonance detection',
         'desc': '64-sample rolling window with Hann windowing. Converts the residual time signal into a frequency spectrum. A sharp, sustained amplitude peak at a fixed frequency is the fingerprint of a Resonance Attack.',
         'output': 'Dominant frequency + amplitude', 'math': 'Window: 64 samples · 320ms'},
        {'num': '03', 'name': 'STFT Tracking', 'role': 'Sweep detection',
         'desc': 'Overlapping FFT windows (64-sample, 75% overlap, 16 windows) track how the dominant frequency shifts over time. A monotonically increasing frequency slope is the fingerprint of a Frequency Sweep Attack.',
         'output': 'Frequency slope Δf/Δt', 'math': 'Step: 16 samples · 75% overlap'},
        {'num': '04', 'name': 'Haar Wavelet', 'role': 'Burst detection',
         'desc': 'O(n) multi-scale decomposition localises brief, high-energy spikes simultaneously in time and frequency — events too short for FFT or STFT to capture. High-frequency detail coefficients flag a Transient Burst Attack.',
         'output': 'Detail coefficient magnitude', 'math': '8 decomposition scales'},
        {'num': '05', 'name': 'Threshold Classifier', 'role': 'Attack classification',
         'desc': 'Physics-constrained decision logic on Core 1. Classifications that violate actuator inertia laws (physically impossible frequency jumps) are automatically rejected as sensor artifacts before output.',
         'output': 'NORMAL / RESONANCE / SWEEP / BURST', 'math': 'Target: F1 ≥ 0.92'},
        {'num': '06', 'name': 'Adaptive Dampening', 'role': 'Active mitigation',
         'desc': 'PWM cutoff adapts to the classified attack type in real time: notch filter for Resonance, moving average for Sweep, clamp for Burst. Motor stabilises within 300ms. SEIS counter increments with Joules prevented.',
         'output': 'Corrected PWM + SEIS in Joules', 'math': 'Latency target: < 300ms'},
    ]

    rows = []
    for layer in layers:
        rows.append(html.Div(style={
            'display': 'grid', 'gridTemplateColumns': '64px 200px 1fr 220px', 'gap': '32px',
            'padding': '24px 40px', 'borderBottom': f'1px solid {BORDER}', 'alignItems': 'start'
        }, children=[
            html.Div(layer['num'], style={
                'fontFamily': MONO_FONT, 'fontSize': '11px', 'fontWeight': '600',
                'letterSpacing': '0.1em', 'color': TEXT_MUTED, 'paddingTop': '2px'
            }),
            html.Div([
                html.Div(layer['name'], style={
                    'fontFamily': SERIF_FONT, 'fontSize': '19px', 'color': TEXT_MAIN,
                    'marginBottom': '4px', 'lineHeight': '1.2'
                }),
                html.Div(layer['role'], style={
                    'fontFamily': MONO_FONT, 'fontSize': '10px', 'letterSpacing': '0.08em',
                    'color': ACCENT_AMBER, 'textTransform': 'uppercase'
                }),
            ]),
            body_text(layer['desc'], {'color': TEXT_MAIN}),
            html.Div([
                html.Div("Output", style={
                    'fontFamily': MONO_FONT, 'fontSize': '9px', 'letterSpacing': '0.1em',
                    'color': TEXT_MUTED, 'textTransform': 'uppercase', 'marginBottom': '3px'
                }),
                html.Div(layer['output'], style={
                    'fontFamily': MONO_FONT, 'fontSize': '11px', 'color': TEXT_MAIN, 'marginBottom': '8px'
                }),
                html.Div(layer['math'], style={
                    'fontFamily': MONO_FONT, 'fontSize': '11px', 'color': TEXT_MUTED,
                    'background': WHITE_PANEL, 'border': f'1px solid {BORDER}',
                    'padding': '6px 10px', 'borderRadius': '3px'
                }),
            ]),
        ]))

    return html.Div([
        table_header({'template': '64px 200px 1fr 220px', 'labels': ['Layer', 'Name', 'Description', 'Parameters']}),
        html.Div(rows),
    ])


# ══════════════════════════════════════════════
# TAB 3 — ATTACK REFERENCE
# ══════════════════════════════════════════════
def _atk_row(label, text, tag=None):
    return html.Div(style={
        'marginBottom': '18px', 'paddingBottom': '18px', 'borderBottom': f'1px solid {BORDER}'
    }, children=[
        html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '6px'}, children=[
            html.Div(label, style={
                'fontFamily': MONO_FONT, 'fontSize': '9px', 'letterSpacing': '0.1em',
                'color': TEXT_MUTED, 'textTransform': 'uppercase'
            }),
            mono_tag(tag) if tag else None,
        ]),
        body_text(text, {'color': TEXT_MAIN}),
    ])

def attacks_tab():
    attacks = [
        {'id': 'Resonance', 'button': 'Button 3 · GPIO 26',
         'mechanism': 'Locks PWM to the motor\'s mechanical resonant frequency. Maximum structural fatigue with minimum command deviation — the motor stays "online" and appears healthy to the network.',
         'detection': 'FFT dominant peak amplitude exceeds threshold at resonant frequency',
         'mitigation': 'Frequency shift → PWM 140 (moves out of harmonic zone)',
         'real_world': 'Pump bearing destruction, HVAC compressor failure', 'pwm': '240'},
        {'id': 'Frequency Sweep', 'button': 'Button 1 · GPIO 12',
         'mechanism': 'Sweeps PWM from 80Hz to 220Hz over 10 seconds, deliberately drifting to evade fixed-frequency detectors. Causes progressive mechanical degradation across multiple frequency bands.',
         'detection': 'STFT frequency slope Δf/Δt exceeds threshold across 16 overlapping windows',
         'mitigation': 'Speed lock → PWM 120 (eliminates variable speed exposure)',
         'real_world': 'Industrial motor wear, HVAC compressor degradation', 'pwm': '80→220'},
        {'id': 'Transient Burst', 'button': 'Button 2 · GPIO 14',
         'mechanism': 'Randomised high-amplitude PWM pulses at irregular intervals. Each pulse is too short for FFT or STFT to capture, but micro-fatigue accumulates over time until catastrophic failure.',
         'detection': 'Haar wavelet detail coefficients exceed magnitude threshold at high frequency scales',
         'mitigation': 'Emergency power cut → PWM 0 (eliminates shock loading)',
         'real_world': 'Servo motor failure, drone actuator degradation', 'pwm': '255 (burst)'},
    ]

    cards = []
    for atk in attacks:
        cards.append(html.Div(style={
            'borderTop': f'2px solid {TEXT_MAIN}', 'padding': '32px 40px',
            'borderBottom': f'1px solid {BORDER}'
        }, children=[
            html.Div(style={
                'display': 'grid', 'gridTemplateColumns': '260px 1fr 260px', 'gap': '48px', 'alignItems': 'start'
            }, children=[

                html.Div([
                    html.H3(atk['id'], style={
                        'fontFamily': SERIF_FONT, 'fontSize': '24px', 'fontWeight': '700',
                        'fontStyle': 'italic', 'color': TEXT_MAIN, 'marginBottom': '8px', 'lineHeight': '1.15'
                    }),
                    html.Div(atk['button'], style={
                        'fontFamily': MONO_FONT, 'fontSize': '10px', 'letterSpacing': '0.1em',
                        'color': ACCENT_AMBER, 'textTransform': 'uppercase', 'marginBottom': '18px'
                    }),
                    html.Div("Simulated PWM", style={
                        'fontFamily': MONO_FONT, 'fontSize': '9px', 'letterSpacing': '0.1em',
                        'color': TEXT_MUTED, 'textTransform': 'uppercase', 'marginBottom': '3px'
                    }),
                    html.Div(atk['pwm'], style={
                        'fontFamily': MONO_FONT, 'fontSize': '18px', 'fontWeight': '700', 'color': TEXT_MAIN
                    }),
                ]),

                html.Div([
                    _atk_row("Mechanism", atk['mechanism']),
                    _atk_row("Detection", atk['detection'], tag="Spectral"),
                    _atk_row("Mitigation", atk['mitigation'], tag="Dampening"),
                ]),

                html.Div([
                    html.Div("Real-world targets", style={
                        'fontFamily': MONO_FONT, 'fontSize': '9px', 'letterSpacing': '0.1em',
                        'color': TEXT_MUTED, 'textTransform': 'uppercase', 'marginBottom': '10px'
                    }),
                    body_text(atk['real_world'], {'color': TEXT_MAIN}),
                ]),
            ]),
        ]))

    return html.Div([
        section_header("Three attacks.\nZero network footprint.",
                        "Each attack class is physically distinct, targets a different mechanical failure mode, and requires a different spectral transform to detect. None of them appear in any network log. All three are simulated in real hardware by the button-press firmware."),
        html.Div(cards),
    ])


# ══════════════════════════════════════════════
# TAB 4 — HARDWARE
# ══════════════════════════════════════════════
def _hw_row(num, part, role, spec):
    return html.Div(style={
        'display': 'grid', 'gridTemplateColumns': '64px 220px 1fr 220px', 'gap': '32px',
        'padding': '22px 40px', 'borderBottom': f'1px solid {BORDER}', 'alignItems': 'start'
    }, children=[
        html.Div(num, style={
            'fontFamily': MONO_FONT, 'fontSize': '11px', 'fontWeight': '600',
            'letterSpacing': '0.1em', 'color': TEXT_MUTED, 'paddingTop': '2px'
        }),
        html.Div(part, style={
            'fontFamily': SERIF_FONT, 'fontSize': '17px', 'color': TEXT_MAIN, 'lineHeight': '1.25'
        }),
        body_text(role, {'color': TEXT_MAIN}),
        html.Div(spec, style={
            'fontFamily': MONO_FONT, 'fontSize': '11px', 'color': TEXT_MUTED,
            'background': WHITE_PANEL, 'border': f'1px solid {BORDER}',
            'padding': '6px 10px', 'borderRadius': '3px', 'display': 'inline-block'
        }),
    ])

def hardware_tab():
    components = [
        {'num': '01', 'part': 'MYOSA Mini IoT Kit (ESP32)',
         'role': 'Dual-core host for the entire detection pipeline — Kalman filtering, spectral analysis, and classification all run on-device with no cloud dependency.',
         'spec': 'ESP32, dual-core 240MHz'},
        {'num': '02', 'part': 'MPU6050 IMU',
         'role': 'Mounted directly on the motor housing. Streams raw accelerometer data into the Kalman filter at 200Hz — the physical sensor feeding every downstream layer.',
         'spec': '6-axis, I²C, 200Hz'},
        {'num': '03', 'part': '5V DC Motor',
         'role': 'The protected actuator. Runs continuously as the physical target for all three simulated attack classes, driven through the L293D motor driver.',
         'spec': '5V, brushed DC'},
        {'num': '04', 'part': 'L293D Motor Driver',
         'role': 'Dual H-bridge driver circuit that manages motor direction and allows logic-level PWM speed and dampening control from the ESP32.',
         'spec': 'Dual H-bridge IC'},
        {'num': '05', 'part': 'SSD1306 OLED',
         'role': 'On-device live dashboard — shows current threat class, active countermeasure, and running SEIS total without needing a connected laptop.',
         'spec': '128×64, I²C monochrome'},
        {'num': '06', 'part': 'Push Buttons',
         'role': 'Tactile button inputs used to trigger simulated attack sequences (Resonance, Frequency Sweep, Transient Burst) directly on the hardware.',
         'spec': 'GPIO digital inputs'},
    ]

    rows = [_hw_row(c['num'], c['part'], c['role'], c['spec']) for c in components]

    return html.Div([
        section_header("Six parts.\nOne actuator. Real sensor data.",
                        "Every reading behind the Live Monitor tab comes from physical hardware — the MPU6050 sits on a real motor, driven through an L293D motor driver circuit. Only the attack triggers are pre-programmed button presses; the vibration signal and every detection outcome are genuine."),
        table_header({'template': '64px 220px 1fr 220px', 'labels': ['No.', 'Component', 'Role in system', 'Spec']}),
        html.Div(rows),

        html.Div(style={
            'marginTop': '40px', 'display': 'grid', 'gridTemplateColumns': '1fr 1fr',
            'gap': '48px', 'padding': '0 40px 40px 40px'
        }, children=[
            html.Div([
                eyebrow("Signal chain"),
                html.Div([
                    html.Span("MPU6050 → ", style={'fontFamily': MONO_FONT, 'fontSize': '13px', 'color': TEXT_MAIN}),
                    html.Span("ESP32 (Kalman → FFT/STFT/Wavelet → classifier) → ", style={'fontFamily': MONO_FONT, 'fontSize': '13px', 'color': TEXT_MAIN}),
                    html.Span("L293D driver → ", style={'fontFamily': MONO_FONT, 'fontSize': '13px', 'color': TEXT_MAIN}),
                    html.Span("5V DC motor", style={'fontFamily': MONO_FONT, 'fontSize': '13px', 'color': TEXT_MAIN}),
                ], style={'background': WHITE_PANEL, 'border': f'1px solid {BORDER}', 'padding': '14px 16px', 'lineHeight': '1.8'}),
            ]),
            html.Div([
                eyebrow("Output chain"),
                html.Div([
                    html.Span("Classifier → ", style={'fontFamily': MONO_FONT, 'fontSize': '13px', 'color': TEXT_MAIN}),
                    html.Span("SSD1306 OLED (live status) + ", style={'fontFamily': MONO_FONT, 'fontSize': '13px', 'color': TEXT_MAIN}),
                    html.Span("Serial → dashboard", style={'fontFamily': MONO_FONT, 'fontSize': '13px', 'color': TEXT_MAIN}),
                ], style={'background': WHITE_PANEL, 'border': f'1px solid {BORDER}', 'padding': '14px 16px', 'lineHeight': '1.8'}),
            ]),
        ]),
    ])


# ══════════════════════════════════════════════
# TAB 5 — ABOUT
# ══════════════════════════════════════════════
def _about_stat(value, label):
    return html.Div([
        html.Div(value, style={
            'fontFamily': SERIF_FONT, 'fontSize': '28px', 'fontStyle': 'italic',
            'color': TEXT_MAIN, 'lineHeight': '1.1', 'marginBottom': '4px'
        }),
        html.Div(label, style={
            'fontFamily': MONO_FONT, 'fontSize': '10px', 'letterSpacing': '0.1em',
            'color': TEXT_MUTED, 'textTransform': 'uppercase'
        }),
    ])

def about_tab():
    contributions = [
        {'name': 'Three-attack taxonomy',
         'desc': 'A physics-first classification of oscillation attacks — Resonance, Frequency Sweep, and Transient Burst — defined by mechanical signature rather than network behaviour.'},
        {'name': 'Adaptive spectral-feedback dampening',
         'desc': 'PWM correction that reads directly from the spectral classifier output, tuning its response (notch filter, moving average, or clamp) to the specific attack class detected.'},
        {'name': 'SEIS metric',
         'desc': 'Security-Energy Impact Score — a single Joule-denominated number quantifying the physical energy cost an attack imposes, independent of whether it was ever logged on the network.'},
    ]

    return html.Div([
        section_header("Cyber-Physical Motor Defense",
                        "ZeroJoule is an edge-based intrusion detection system for IoT actuators, built for the IEEE MYOSA Event 6.0 competition on the MYOSA Mini IoT Kit. It targets a class of attacks that conventional network-layer IDS can't see: oscillation attacks that manipulate an actuator's physical behaviour directly, leaving no trace in packet logs."),

        # Stats row
        html.Div(style={
            'display': 'grid', 'gridTemplateColumns': 'repeat(4, 1fr)',
            'borderTop': f'1px solid {BORDER}', 'borderBottom': f'1px solid {BORDER}',
            'padding': '28px 40px', 'marginBottom': '40px'
        }, children=[
            _about_stat('3', 'Attack classes'),
            _about_stat('6', 'Pipeline layers'),
            _about_stat('<300ms', 'Detection latency target'),
            _about_stat('0', 'Cloud dependencies'),
        ]),

        # Novel contributions
        html.Div(style={'padding': '0 40px', 'marginBottom': '40px'}, children=[
            eyebrow("Novel contributions"),
            html.Div([
                html.Div(style={'padding': '20px 0', 'borderBottom': f'1px solid {BORDER}'}, children=[
                    html.Div(c['name'], style={
                        'fontFamily': SERIF_FONT, 'fontSize': '18px', 'color': TEXT_MAIN, 'marginBottom': '6px'
                    }),
                    body_text(c['desc'], {'color': TEXT_MAIN}),
                ]) for c in contributions
            ]),
        ]),

        # Team + competition
        html.Div(style={
            'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '48px',
            'padding': '0 40px 40px 40px'
        }, children=[
            html.Div([
                eyebrow("Team"),
                body_text(
                    "Developed by Kezita, and Jeslyn, under the mentorship of Dr. Raja Varma Pamba at Manipal Academy of Higher Education, Dubai.",
                    {'color': TEXT_MAIN}
                ),
            ]),
            html.Div([
                eyebrow("Competition"),
                body_text(
                    "Submitted to IEEE MYOSA Event 6.0.",
                    {'color': TEXT_MAIN}
                ),
            ]),
        ]),
    ])


# --- LAYOUT ---
_PANEL_IDS = ['tab-live', 'tab-pipeline', 'tab-attacks', 'tab-hardware', 'tab-about']

app.layout = html.Div(style={
    'backgroundColor': BG, 'color': TEXT_MAIN, 'fontFamily': MONO_FONT, 'padding': '0', 'minHeight': '100vh'
}, children=[

    # Header Bar
    html.Div(style={
        'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
        'padding': '24px 40px', 'borderBottom': f'1px solid {BORDER}'
    }, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '14px'}, children=[
            html.Div([
                html.Span("ZEROJOULE", style={
                    'fontSize': '17px', 'fontWeight': '800', 'letterSpacing': '2px', 'fontFamily': MONO_FONT
                }),
                html.Span("  ·  Cyber-Physical Motor Defense", style={
                    'fontSize': '13px', 'color': TEXT_MUTED, 'fontFamily': MONO_FONT, 'fontWeight': '400'
                })
            ])
        ]),
        html.Div("MYOSA · MPU6050 200HZ", style={
            'fontSize': '12px', 'color': TEXT_MUTED, 'fontFamily': MONO_FONT, 'letterSpacing': '1.5px'
        })
    ]),

    # Tabs
    html.Div(style={'padding': '0 40px', 'marginTop': '20px'}, children=[
        dcc.Tabs(id='tabs', value='tab-live', children=[
            dcc.Tab(label='Live Monitor', value='tab-live'),
            dcc.Tab(label='Pipeline', value='tab-pipeline'),
            dcc.Tab(label='Attack Reference', value='tab-attacks'),
            dcc.Tab(label='Hardware', value='tab-hardware'),
            dcc.Tab(label='About', value='tab-about'),
        ]),
    ]),

    # All panels mounted permanently
    html.Div(style={'paddingBottom': '60px'}, children=[
        html.Div(id='panel-tab-live', children=live_tab_content()),
        html.Div(id='panel-tab-pipeline', children=pipeline_tab(), style={'display': 'none'}),
        html.Div(id='panel-tab-attacks', children=attacks_tab(), style={'display': 'none'}),
        html.Div(id='panel-tab-hardware', children=hardware_tab(), style={'display': 'none'}),
        html.Div(id='panel-tab-about', children=about_tab(), style={'display': 'none'}),
    ]),

    dcc.Interval(id='graph-update', interval=200, n_intervals=0)
])


# --- TAB VISIBILITY TOGGLE ---
@app.callback(
    [Output(f'panel-{pid}', 'style') for pid in _PANEL_IDS],
    Input('tabs', 'value')
)
def toggle_tabs(selected):
    return [{'display': 'block'} if pid == selected else {'display': 'none'} for pid in _PANEL_IDS]


# --- DASHBOARD CALLBACK ---
@app.callback(
    [Output('live-graph', 'figure'),
     Output('alert-banner', 'children'),
     Output('alert-banner', 'style'),
     Output('card-threat', 'children'),
     Output('card-threat', 'style'),
     Output('card-action', 'children'),
     Output('card-vibe', 'children'),
     Output('card-seis', 'children')],
    [Input('graph-update', 'n_intervals')]
)
def update_live_telemetry(n):
    with buffer_lock:
        time_list = list(time_buffer)
        vibe_list = list(vibe_buffer)
        attack_list = list(attack_buffer)
        damp_list = list(dampening_buffer)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=time_list, y=vibe_list,
        name="Vibration (G-Force)", line=dict(color=TEXT_MAIN, width=2)
    ))

    fig.add_trace(go.Scatter(
        x=time_list, y=attack_list,
        name="Threat Class", line=dict(color=ACCENT_RED, width=1.5, dash='dot')
    ))

    fig.add_trace(go.Scatter(
        x=time_list, y=damp_list,
        name="Mitigation Active", line=dict(color=ACCENT_AMBER, width=2)
    ))

    fig.update_layout(
        paper_bgcolor=WHITE_PANEL, plot_bgcolor=WHITE_PANEL,
        font=dict(color=TEXT_MAIN, family=MONO_FONT, size=12),
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(title="Time", gridcolor=BORDER, zerolinecolor=TEXT_MAIN),
        yaxis=dict(title="Level / Magnitude", gridcolor=BORDER, zerolinecolor=TEXT_MAIN, range=[-5, 110]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                     font=dict(size=11))
    )

    current_vibe = f"{vibe_buffer[-1]:.2f} G" if len(vibe_buffer) > 0 else "0.00 G"
    seis_text = f"{current_status['seis']:.3f} J"

    if current_status['active']:
        banner_text = [
            html.Span("● THREAT DETECTED: ", style={
                'color': ACCENT_RED, 'fontWeight': '700', 'fontFamily': MONO_FONT, 'fontSize': '13px',
                'letterSpacing': '1px'
            }),
            html.Span(current_status['class'], style={
                'color': TEXT_MAIN, 'fontWeight': '700', 'fontFamily': MONO_FONT, 'fontSize': '13px'
            }),
            html.Span(f"   —   mitigation: {current_status['action']}", style={
                'color': TEXT_MUTED, 'fontFamily': MONO_FONT, 'fontSize': '13px'
            })
        ]
        threat_style = {'color': ACCENT_RED, 'fontFamily': MONO_FONT}
        banner_style = {
            'padding': '18px 40px', 'borderBottom': f'1px solid {BORDER}',
            'borderLeft': f'4px solid {ACCENT_RED}', 'backgroundColor': '#FBF1EF'
        }
    else:
        banner_text = [
            html.Span("● SYSTEM SECURE", style={
                'color': ACCENT_GREEN, 'fontWeight': '700', 'fontFamily': MONO_FONT, 'fontSize': '13px',
                'letterSpacing': '1px'
            }),
            html.Span("   —   normal operation, edge safeguards active", style={
                'color': TEXT_MUTED, 'fontFamily': MONO_FONT, 'fontSize': '13px'
            })
        ]
        threat_style = {'color': TEXT_MAIN, 'fontFamily': MONO_FONT}
        banner_style = {
            'padding': '18px 40px', 'borderBottom': f'1px solid {BORDER}',
            'borderLeft': f'4px solid {ACCENT_GREEN}', 'backgroundColor': BG
        }

    return fig, banner_text, banner_style, current_status['class'], threat_style, current_status['action'], current_vibe, seis_text


if __name__ == '__main__':
    app.run(debug=False, port=8050)