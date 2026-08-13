# Robotics & Automation Expert Knowledge - Arduino Basics

## What is Arduino?
Arduino is an open-source electronics platform based on easy-to-use hardware and software. It consists of a physical programmable circuit board (microcontroller) and a piece of software (IDE) that runs on your computer.

## Key Components
- **Microcontroller:** The "brain" of the board (e.g., ATmega328P).
- **Digital I/O Pins:** Used for digital input (sensors) and output (LEDs).
- **Analog Pins:** Used for reading analog sensors (potentiometers, light sensors).
- **USB Plug:** For power and programming.

## Basic Structure (Blink Example)
```cpp
// The setup function runs once when you press reset or power the board
void setup() {
  // initialize digital pin LED_BUILTIN as an output.
  pinMode(LED_BUILTIN, OUTPUT);
}

// The loop function runs over and over again forever
void loop() {
  digitalWrite(LED_BUILTIN, HIGH);   // turn the LED on
  delay(1000);                       // wait for a second
  digitalWrite(LED_BUILTIN, LOW);    // turn the LED off
  delay(1000);                       // wait for a second
}
```

## Sensors & Actuators
- **Inputs:** Ultrasonic sensors, IR sensors, LDRs, Buttons.
- **Outputs:** Motors (Servo, DC, Stepper), LEDs, LCD screens.

## Next Steps
- Learn about **PWM (Pulse Width Modulation)** for speed control.
- Explore **I2C and SPI** communication protocols.
- Build a simple **Line Follower Robot**.
