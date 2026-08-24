---
publishDate: 2026-08-24T00:00:00Z
title: ZeroJoule
excerpt: Edge-computing cyber-physical defense system that detects and mitigates physics-layer oscillation attacks on IoT actuators using a six-layer Kalman/spectral pipeline and a Security-Energy Impact Score.
image: /assets/images/zerojoule/zerojoule-cover.png
tags:
  - IoT Security
  - Edge Computing
  - ESP32
  - Cyber-Physical Systems
  - MYOSA
  - Kalman Filter
  - FFT
---

> Detect and stop physical attacks on motors before they cause damage; all on-device, targeting sub-300ms, no cloud dependency.

---

## Acknowledgements

We would like to express our sincere gratitude to Dr. Raja Varma Pamba, our faculty mentor, for her invaluable guidance and support throughout this project. We also extend our thanks to the MYOSA team for providing the hardware platform and resources that made this project possible, and to Manipal Academy of Higher Education, Dubai, for fostering an environment of innovation and research.

---

## Overview

ZeroJoule is an edge-based intrusion detection and cyber-physical defense system built for IoT actuators such as motors, pumps, fans, and compressors. It targets physical oscillation attacks: commands that are syntactically valid and pass every network-layer inspection, but instruct actuators to run at frequencies that induce destructive mechanical resonance. Standard network IDS tools cannot see these attacks because no malicious traffic or packet-log evidence is ever generated. The damage happens purely at the physical layer.

ZeroJoule is built for industrial IoT operators, smart building and factory automation teams, and actuator/equipment manufacturers who need to protect motor-driven infrastructure such as pumps, fans, compressors, and conveyor motors from attacks that conventional network security can't see.

ZeroJoule shifts detection to where the attack actually happens: the motor's own vibration signature. It runs entirely on-device with no cloud dependency, targeting sub-300ms detection-to-mitigation latency. The project introduces a physical attack taxonomy, an adaptive spectral-feedback dampening mechanism, and a custom Security-Energy Impact Score (SEIS) that quantifies attack damage directly in Joules.

**Key Features:**

- Six-layer on-device detection and defense pipeline
- Kalman filtering for vibration noise removal
- Triple spectral analysis (FFT + STFT + Haar-style wavelet)
- Threshold-based attack classification
- Adaptive PWM dampening, tailored per attack type
- Security-Energy Impact Score (SEIS) measured in Joules
- Live OLED on-device dashboard
- Real-time web dashboard (Python/Dash/Plotly) with live telemetry, pipeline breakdown, attack reference, and hardware spec tabs
- No cloud dependency

---

## Demo / Examples

### Live Demonstration

The full cycle is under two minutes and repeatable on demand.

**Step 1: Baseline**
The motor runs at normal operating speed after a 150ms full-power kickstart pulse (PWM 255) to overcome static friction. The OLED shows a flat FFT spectrum, a "SYSTEM NORMAL" flag, and SEIS at 0.00J. A 2-second unprotected window lets judges observe raw physical attack distortion before mitigation engages.

**Step 2: Resonance Attack** (GPIO 26)
PWM locks to the motor's resonant frequency (PWM 240). The motor visibly and audibly oscillates. FFT amplitude crosses the 5.0 threshold, classifying as Class 25. Adaptive dampening shifts the frequency to PWM 140, moving the motor out of the harmonic danger zone within 300ms. SEIS ticks up with the exact Joules saved.

**Step 3: Frequency Sweep Attack** (GPIO 12)
PWM sweeps 80Hz → 220Hz over 10 seconds. STFT tracks the drifting frequency ridge; once the slope exceeds 1.5, the system classifies as Class 50 and engages a Safe Duty Cycle Lock at PWM 120.

**Step 4: Transient Burst Attack** (GPIO 14)
Randomized high-amplitude pulses fire at PWM 255. Wavelet detail coefficients spike; once the spike exceeds 30.0, the system classifies as Class 75 and triggers an Emergency Soft Power Cut to PWM 0.

**Step 5: System Reset** (GPIO 27)
A manual push button returns the system to baseline, replacing the non-functional APDS9960 gesture sensor.

### Images

<p align="center">
<img src="/assets/images/zerojoule/zerojoule-cover.png" width="800">
<br/>
<i>Complete ZeroJoule hardware setup with MYOSA board, MPU6050, and OLED display</i>
</p>

<p align="center">
<img src="/assets/images/zerojoule/setup.jpg" width="800">
<br/>
<i>MYOSA motherboard with sensors connected via JST cables</i>
</p>

<p align="center">
<img src="/assets/images/zerojoule/oled-dashboard.jpg" width="800">
<br/>
<i>OLED dashboard showing FFT spectrum, attack status, and SEIS counter</i>
</p>

<p align="center">
<img src="/assets/images/zerojoule/mpu6050-mounting.jpg" width="800">
<br/>
<i>MPU6050 mounted on motor housing, isolated from board vibration</i>
</p>

<p align="center">
<img src="/assets/images/zerojoule/driver-circuit.jpg" width="800">
<br/>
<i>L293D motor driver circuit</i>
</p>

### Videos

<video controls width="100%">
<source src="/zerojoule-demo.mp4" type="video/mp4">
</video>

<video controls width="100%">
<source src="/zerojoule-tech.mp4" type="video/mp4">
</video>

---

## Features (Detailed)

### 1. Kalman Filter (Layer 1: Core 0, 200Hz)

Recursive Bayesian estimator that filters sensor noise and electrical interference from raw MPU6050 vibration data, producing a residual signal:

r(k) = z(k) − H·x̂(k|k−1)

This residual represents deviation from normal operation and is the input to every downstream layer. Under normal operation the residual is near-zero-mean noise; under attack, it carries the attack signature.

### 2. Fast Fourier Transform (Layer 2)

Converts the residual into a frequency spectrum over a 64-sample rolling Hamming window, isolating sharp peaks characteristic of fixed-frequency resonance.

### 3. Short-Time Fourier Transform (Layer 3)

Tracks frequency shifts over time by comparing the peak frequency across successive FFT windows, identifying rate-of-change frequency slopes, the sweep attack's signature.

### 4. Wavelet-Style Transient Detection (Layer 4)

Single-level Haar-style pairwise detail coefficient computation, catching short high-energy transients that FFT/STFT windowing misses.

### 5. Threshold-Based Attack Classification (Layer 5: Core 1)

Deterministic, zero-training-data classifier running on three key metrics derived from the spectral analysis.

| Attack Type | Metric | Threshold | Class | Mitigation Action |
|---|---|---|---|---|
| Resonance | FFT Vibe Amplitude | > 5.0 | Class 25 | Frequency Shift → PWM 140 |
| Sweep | STFT Frequency Slope | > 1.5 | Class 50 | Safe Duty Cycle Lock → PWM 120 |
| Burst | Wavelet Detail Spike | > 30.0 | Class 75 | Emergency Soft Power Cut → PWM 0 |

Sub-10ms classification latency. Telemetry streamed continuously over USB Serial (115200 baud) as `Attack_Class, Dampening_Active, Vibe_Amplitude`. Thresholds were determined empirically through iterative testing on this hardware configuration (see Limitations below).

### 6. Adaptive Dampening (Layer 6)

Dynamically alters motor PWM depending on active threat class, and logs prevented energy impact via SEIS.

### 7. Security-Energy Impact Score (SEIS)

SEIS = ∫₀ᵀ [P_attack(t) − P_normal(t)] dt

Power is estimated as proportional to the square of the PWM duty cycle. This is documented as an estimate, not a precision power measurement.

Note: the 150ms motor kickstart pulse (full PWM 255 to overcome static friction) is not currently captured in the SEIS integration, so the reported Joules reflect steady-state attack energy rather than the full startup transient.

### 8. Real-Time Web Dashboard

Python/Dash/Plotly application with a multi-threaded architecture: a background thread continuously reads, decodes, and parses serial strings from the ESP32 over COM3 at 115200 baud, with auto-reconnection logic and thread-locked circular buffers holding the last 50 data points (time, vibration amplitude, attack class, dampening state). Styled in a cream/editorial layout with tabs for live telemetry, pipeline breakdown, attack reference, hardware specs, and project metadata.

### 9. Hardware Implementation

**MYOSA Motherboard:** ESP32 dual-core, 240MHz, 520KB SRAM, 4MB flash

**Sensors:** MPU6050 (6-axis, 200Hz, I2C on GPIO 21/22), SSD1306 OLED (128x64, I2C, 0x3C)

**Actuator:** 5V DC motor driven by an L293D dual H-bridge for logic-level PWM speed/dampening control

**GPIO Assignments:**
- Resonance trigger (B3): GPIO 26
- Sweep trigger (B1): GPIO 12
- Burst trigger (B2): GPIO 14
- Reset (B4): GPIO 27
- Motor IN1: GPIO 19
- Motor IN2: GPIO 18

### Limitations

This is a proof-of-concept prototype validated on a single motor/sensor rig, not a field-tested industrial system.

- Threshold values (5.0, 1.5, 30.0) were determined empirically through iterative testing on this specific hardware configuration; validation across additional motor/sensor pairs is a direction for future work.
- SEIS energy figures are estimates derived from PWM duty cycle, not direct current/voltage measurement.
- No sensor spoofing detection: if the MPU6050 data itself is fed fabricated values, the pipeline currently has no way to detect that the vibration input is untrustworthy.
- Classification is threshold-based rather than learned, so it does not generalize beyond the three attack classes it was designed to catch.

### Future Directions

- Quantitative validation across repeated trials (false-positive/false-negative rates, timing distribution).
- Testing against real network-delivered attack vectors, not just firmware-simulated ones.
- Threshold auto-calibration or a lightweight learned classifier to generalize across different motors and mounts.
- Multi-actuator deployment and testing (pumps, fans, compressors) beyond the single DC motor used here.
- Direct current/voltage sensing for a precision SEIS measurement instead of the current PWM-based estimate.

---

## Usage Instructions

### Hardware Requirements
- MYOSA Mini IoT Kit (ESP32 motherboard, MPU6050, OLED)
- 5V DC motor (plain shaft)
- L293D dual H-bridge motor driver IC
- Push buttons (4x: resonance, sweep, burst, reset)
- 830-point breadboard and jumper wires

### Software Requirements
- Arduino IDE with ESP32 support
- Arduino libraries: Adafruit MPU6050, Adafruit Sensor, SimpleKalmanFilter, arduinoFFT, Adafruit GFX, Adafruit SSD1306
- Python 3.x with: `dash`, `plotly`, `pyserial`, `pandas`

### Installation
1. Clone or download the ZeroJoule repository
2. Install Arduino libraries via Library Manager
3. Upload firmware to the MYOSA board
4. Connect MPU6050 and OLED via JST cables
5. Wire the L293D driver circuit on breadboard
6. Install Python dependencies: `pip install dash plotly pyserial pandas`
7. Run the dashboard: `py app.py`

### Circuit Assembly

1. Mount MPU6050 on motor housing, isolated from the board.
2. Place the L293D driver IC straddling the breadboard's center trough, pins on rows 10–17 (E10–E17 on one side, I10–I17 on the other).
3. Wire power rails: D10, D17, J10, J17 → red (+) rail; D13, D14, D16, J11 → blue (–) rail. Connect ESP32 GND → blue rail, VIN → red rail.
4. Connect the motor: black wire → J12, red wire → J15.
5. Connect L293D direction pins: Motor IN1 → ESP32 GPIO 19; Motor IN2 → ESP32 GPIO 18.
6. Connect MPU6050, OLED, and MYOSA motherboard to each other via JST cables (I2C daisy chain).
7. Place four push buttons across the breadboard trough at E30, E35, E40, E45:
   - B1 (Sweep): D30 → ESP32 GPIO 12; D32 → blue (–) rail
   - B2 (Burst): D35 → ESP32 GPIO 14; D37 → blue (–) rail
   - B3 (Resonance): D40 → ESP32 GPIO 26; D42 → blue (–) rail
   - B4 (Reset): D45 → ESP32 GPIO 27; D47 → blue (–) rail
8. All four button GPIOs are configured as `INPUT_PULLUP` in firmware; buttons pull to GND when pressed, so a press reads LOW.

### Operation
1. Power on the system and confirm baseline (SYSTEM NORMAL, 0.00J)
2. Press attack buttons to inject resonance, sweep, or burst attacks
3. Observe detection and dampening on the OLED and/or web dashboard
4. Press reset between cycles

```bash
py app.py
```

### Firmware Code Highlights (`zerojoule.ino`)

Full source available in the repository as `zerojoule.ino`. Core classification and mitigation logic below:

```cpp
// 6. Threat Classification
if (!motorOn) {
  currentAttack = NORMAL;
} else if (millis() - attackStartTimer < 2000) {
  currentAttack = NORMAL;
} else if (resonanceMode && vibeAmplitude > 5.0) {
  currentAttack = RESONANCE;
} else if (sweepMode && freqSlope > 1.5) {
  currentAttack = SWEEP;    
} else if (burstActive && waveletDetailSpike > 30.0) {
  currentAttack = BURST;    
} else {
  currentAttack = NORMAL;    
}

// 7. Dynamic PWM Determination & Mitigation Setup
int finalPWM = currentPWM;

if (motorOn) {
  if (currentAttack != NORMAL) dampeningActive = true;

  if (dampeningActive) {
    switch (currentAttack) {
      case BURST: finalPWM = 0; break;
      case SWEEP: finalPWM = 120; break;
      case RESONANCE: finalPWM = 140; break;
      default: break;
    }
  } else {
    if (burstActive || resonanceMode) {
      currentPWM = 240;
    } else if (sweepMode) {
      currentPWM += sweepStep;
      if (currentPWM >= 245 || currentPWM <= 130) sweepStep = -sweepStep;
    }
    finalPWM = currentPWM;
  }
}

// SEIS Joules integration
float calculate_power(uint8_t pwm_val) {
    float duty_cycle = (float)pwm_val / 255.0;
    return P_MAX * (duty_cycle * duty_cycle);
}

void update_SEIS(uint8_t active_pwm, bool is_attacking) {
    unsigned long now = millis();
    float dt = (now - lastEnergyTime) / 1000.0;
    lastEnergyTime = now;

    if ((is_attacking || active_pwm > BASELINE_PWM) && dt < 1.0) {
        float p_current = calculate_power(active_pwm);
        float p_baseline = calculate_power(BASELINE_PWM);
        float p_wasted = p_current - p_baseline;
        if (p_wasted > 0) total_wasted_joules += p_wasted * dt;
    }
}
```

Full version in `zerojoule.ino` includes sensor sampling, FFT/STFT/wavelet computation, button debouncing, and OLED rendering.

### Dashboard Code Highlights (`app.py`)

Full source available in the repository as `app.py`. Core serial-parsing logic below:

```python
# --- SERIAL THREAD (core parsing loop) ---
def read_serial():
    global current_status
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not line or "Attack_Class" not in line:
                continue

            parts = line.split(',')
            data = {k.strip(): float(v.strip()) for k, v in (p.split(':', 1) for p in parts)}

            attack_val = int(data.get('Attack_Class', 0))
            damp_val = int(data.get('Dampening_Active', 0))
            vibe_val = data.get('Vibe_Amplitude', 0.0)
            seis_val = data.get('SEIS', 0.0)

            with buffer_lock:
                time_buffer.append(time.strftime('%H:%M:%S'))
                attack_buffer.append(attack_val)
                dampening_buffer.append(damp_val)
                vibe_buffer.append(vibe_val)

            current_status = {
                "class": attack_labels.get(attack_val, "UNKNOWN"),
                "active": damp_val > 0,
                "seis": seis_val
            }
```

Full version in `app.py` includes auto-reconnection handling, malformed-line recovery, and the Dash callback that renders this into the live graph and status cards.

---

## Tech Stack

- **Embedded Platform:** ESP32 (MYOSA Motherboard)
- **Sensors:** MPU6050, SSD1306 OLED
- **Actuator Driver:** L293D dual H-bridge
- **Signal Processing:** Kalman Filter, FFT, STFT, Haar-style wavelet detail detection
- **Classification:** Threshold-based (deterministic)
- **Communication:** I2C, PWM, USB Serial (115200 baud)
- **Dashboard:** Python, Dash, Plotly
- **Development Environment:** Arduino IDE

---

## Requirements / Installation

```bash
pip install dash plotly pyserial pandas
```

Arduino Library Manager: `Adafruit MPU6050`, `Adafruit Sensor`, `SimpleKalmanFilter`, `arduinoFFT`, `Adafruit GFX`, `Adafruit SSD1306`

---

## File Structure

```
/zerojoule
├─ zerojoule.md
├─ zerojoule-demo.mp4
├─ zerojoule-tech.mp4
├─ zerojoule.ino
├─ app.py
└─ assets/
    └─ images/
        └─ zerojoule/
            ├─ zerojoule-cover.png
            ├─ setup.jpg
            ├─ oled-dashboard.jpg
            ├─ mpu6050-mounting.jpg
            └─ driver-circuit.jpg
```
---

## License

This project is licensed under the MIT License.

---

## Contribution Notes

This project was built by Jeslyn Liz Jacob and Kezita Jebastine for IEEE MYOSA 6.0, under the mentorship of Dr. Raja Varma Pamba, at Manipal Academy of Higher Education, Dubai.