#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include <SimpleKalmanFilter.h>
#include "arduinoFFT.h"
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// --- OLED DISPLAY SETUP ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// --- HARDWARE PIN DEFINITIONS ---
#define MOTOR_IN1 19
#define MOTOR_IN2 18
#define BTN1_PIN 12  // BTN1: Sweep Attack
#define BTN2_PIN 14  // BTN2: Burst Attack
#define BTN3_PIN 26  // BTN3: Resonance Attack
#define BTN4_PIN 27  // BTN4: Reset / Stop

#define PWM_FREQ 5000
#define PWM_RES 8

#define SAMPLES 64          
#define SAMPLING_FREQ 200    

Adafruit_MPU6050 mpu;
SimpleKalmanFilter kalmanRoll(2, 2, 0.01);
ArduinoFFT<double> FFT = ArduinoFFT<double>();

double vReal[SAMPLES];
double vImag[SAMPLES];
unsigned long samplingPeriodUs;

// STFT History Buffer
double stftHistory[3] = {0, 0, 0};

// System States & Timers
bool motorOn = false;
bool sweepMode = false;
bool burstActive = false;
bool resonanceMode = false;

int currentPWM = 0;
int sweepStep = 15;

unsigned long attackStartTimer = 0;
unsigned long kickstartTimer = 0;
unsigned long lastBtnPress = 0;

enum AttackType { NORMAL = 0, RESONANCE = 1, SWEEP = 2, BURST = 3 };
AttackType currentAttack = NORMAL;

bool dampeningActive = false;

// ==================== SEIS ENERGY CALCULATOR ====================
float total_wasted_joules = 0.0;
unsigned long lastEnergyTime = 0;

const float V_SUPPLY = 5.0;           // 5 Volts
const float I_MAX = 0.5;              // 0.5 Amps peak draw
const float P_MAX = V_SUPPLY * I_MAX; // 2.5 Watts max
const float BASELINE_PWM = 120.0;     // Normal operational PWM

// Power calculation proportional to square of duty cycle
float calculate_power(uint8_t pwm_val) {
    float duty_cycle = (float)pwm_val / 255.0;
    return P_MAX * (duty_cycle * duty_cycle);
}

// Integrates power consumption across dt to accumulate real-time Joules
void update_SEIS(uint8_t active_pwm, bool is_attacking) {
    unsigned long now = millis();
    float dt = (now - lastEnergyTime) / 1000.0; // Time in seconds
    lastEnergyTime = now;

    if ((is_attacking || active_pwm > BASELINE_PWM) && dt < 1.0) {
        float p_current = calculate_power(active_pwm);
        float p_baseline = calculate_power(BASELINE_PWM);
       
        float p_wasted = p_current - p_baseline;
        if (p_wasted > 0) {
            total_wasted_joules += p_wasted * dt;
        }
    }
}

void updateOLED(double vibe);

void setup() {
  Serial.begin(115200);

  // Configure Motor Outputs
  ledcAttach(MOTOR_IN1, PWM_FREQ, PWM_RES);
  ledcAttach(MOTOR_IN2, PWM_FREQ, PWM_RES);
  ledcWrite(MOTOR_IN1, 0);
  ledcWrite(MOTOR_IN2, 0);

  // Configure Buttons with Pullup Resistors
  pinMode(BTN1_PIN, INPUT_PULLUP);
  pinMode(BTN2_PIN, INPUT_PULLUP);
  pinMode(BTN3_PIN, INPUT_PULLUP);
  pinMode(BTN4_PIN, INPUT_PULLUP);

  Wire.begin(21, 22);
  Wire.setClock(400000); // Increased I2C speed to prevent sampling lag

  // OLED Display Init
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("OLED Allocation Failed"));
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(15, 25);
  display.println(F("SEIS INITIALIZING..."));
  display.display();

  // MPU6050 Accelerometer Init
  if (mpu.begin(0x69, &Wire)) {
    mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  }

  samplingPeriodUs = round(1000000.0 * (1.0 / SAMPLING_FREQ));
  lastEnergyTime = millis();
}

void loop() {
  unsigned long now = millis();

  // 1. Controls with Kickstart & Debouncing
  if (digitalRead(BTN1_PIN) == LOW && (now - lastBtnPress > 300)) {
    motorOn = true; sweepMode = true; burstActive = false; resonanceMode = false;
    currentPWM = 180; dampeningActive = false;
    attackStartTimer = millis();
    kickstartTimer = millis();
    lastBtnPress = now;
  }

  if (digitalRead(BTN2_PIN) == LOW && (now - lastBtnPress > 300)) {
    motorOn = true; burstActive = true; sweepMode = false; resonanceMode = false;
    currentPWM = 255; dampeningActive = false;
    attackStartTimer = millis();
    kickstartTimer = millis();
    lastBtnPress = now;
  }

  if (digitalRead(BTN3_PIN) == LOW && (now - lastBtnPress > 300)) {
    motorOn = true; resonanceMode = true; sweepMode = false; burstActive = false;
    currentPWM = 240; dampeningActive = false;
    attackStartTimer = millis();
    kickstartTimer = millis();
    lastBtnPress = now;
  }

  // BTN 4: System Reset
  if (digitalRead(BTN4_PIN) == LOW) {
    motorOn = false; sweepMode = false; burstActive = false; resonanceMode = false;
    currentPWM = 0; dampeningActive = false; currentAttack = NORMAL;
    total_wasted_joules = 0.0; // Reset Joules Counter
  }

  // 2. Accelerometer Sampling
  unsigned long microseconds;
  sensors_event_t a, g, temp;

  for (int i = 0; i < SAMPLES; i++) {
    microseconds = micros();
    mpu.getEvent(&a, &g, &temp);

    float rawRoll = atan2(a.acceleration.y, a.acceleration.z) * 180.0 / M_PI;
    float filteredRoll = kalmanRoll.updateEstimate(rawRoll);
    vReal[i] = a.acceleration.z - (filteredRoll / 10.0);
    vImag[i] = 0.0;

    while ((micros() - microseconds) < samplingPeriodUs) {}
  }

  // 3. FFT Analysis
  FFT.windowing(vReal, SAMPLES, FFT_WIN_TYP_HAMMING, FFT_FORWARD);
  FFT.compute(vReal, vImag, SAMPLES, FFT_FORWARD);
  FFT.complexToMagnitude(vReal, vImag, SAMPLES);

  double peakFreq = FFT.majorPeak(vReal, SAMPLES, SAMPLING_FREQ);

  double vibeAmplitude = 0;
  for (int i = 2; i < SAMPLES / 2; i++) {
    if (vReal[i] > vibeAmplitude) vibeAmplitude = vReal[i];
  }

  // 4. STFT Slope Analysis
  stftHistory[0] = stftHistory[1];
  stftHistory[1] = stftHistory[2];
  stftHistory[2] = peakFreq;
  double freqSlope = abs(stftHistory[2] - stftHistory[0]);

  // 5. Wavelet Spike Detection
  double waveletDetailSpike = 0;
  for (int i = 0; i < SAMPLES / 2; i++) {
    double detail = (vReal[2 * i] - vReal[2 * i + 1]) / 1.414;
    if (abs(detail) > waveletDetailSpike) waveletDetailSpike = abs(detail);
  }

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

    // Apply Kickstart or Steady State Duty Cycle
    if (millis() - kickstartTimer < 150) {
      ledcWrite(MOTOR_IN1, 0);
      ledcWrite(MOTOR_IN2, 255);
    } else {
      ledcWrite(MOTOR_IN1, 0);
      ledcWrite(MOTOR_IN2, finalPWM);
    }
  } else {
    ledcWrite(MOTOR_IN1, 0);
    ledcWrite(MOTOR_IN2, 0);
    finalPWM = 0;
  }

  // 8. UPDATE CONTINUOUS SEIS JOULES
  bool is_attacking = motorOn && (resonanceMode || sweepMode || burstActive);
  update_SEIS(finalPWM, is_attacking);

  // 9. Telemetry Stream to Serial Monitor
  Serial.print("Attack_Class:");
  Serial.print(currentAttack * 25);
  Serial.print(",Dampening_Active:");
  Serial.print(dampeningActive ? 1 : 0);
  Serial.print(",Vibe_Amplitude:");
  Serial.print(motorOn ? vibeAmplitude : 0.0);
  Serial.print(",SEIS:");
  Serial.println(total_wasted_joules, 3);

  // 10. OLED Refresh
  updateOLED(motorOn ? vibeAmplitude : 0);
}

// --- OLED RENDERING LOGIC ---
void updateOLED(double vibe) {
  display.clearDisplay();
 
  if (!dampeningActive) {
    display.drawRect(0, 0, 128, 64, SSD1306_WHITE);
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
   
    display.setCursor(8, 4);
    display.println(F("SEIS DEFENSE SYSTEM"));
   
    display.setCursor(8, 18);
    display.print(F("STATUS: "));
    display.println(motorOn ? F("MONITORING") : F("STANDBY"));
   
    display.setCursor(8, 32);
    display.print(F("SEIS SCORE: "));
    display.print(total_wasted_joules, 2);
    display.println(F(" J"));

    display.setCursor(8, 46);
    display.println(F("SYSTEM SECURE"));
  } else {
    display.fillRect(0, 0, 128, 16, SSD1306_WHITE);
    display.setTextSize(1);
    display.setTextColor(SSD1306_BLACK);
    display.setCursor(12, 4);
    display.println(F("!! THREAT DETECTED !!"));
   
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(5, 22);
    display.print(F("SEIS WASTED: "));
    display.print(total_wasted_joules, 2);
    display.println(F(" J"));
   
    display.setCursor(5, 36);
    display.print(F("ACTION: "));
    switch (currentAttack) {
      case BURST:     display.println(F("POWER CUT")); break;
      case SWEEP:     display.println(F("LOCK 120PWM")); break;
      case RESONANCE: display.println(F("FREQ SHIFT")); break;
      default:        display.println(F("ACTIVE")); break;
    }

    display.setCursor(5, 50);
    display.println(F("MITIGATION ENGAGED"));
  }
 
  display.display();
}