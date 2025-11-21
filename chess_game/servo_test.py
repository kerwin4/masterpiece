import subprocess
import time
from gpiozero import Servo
from gpiozero.pins.pigpio import PiGPIOFactory

SERVO_PIN = 13
DELAY = 2

# === Start the pigpio daemon ===
try:
    subprocess.run(["sudo", "pigpiod"], check=True)
    time.sleep(1)  # Give daemon time to start
except subprocess.CalledProcessError:
    print("Failed to start pigpiod. Is it installed?")

# === Initialize servo using pigpio ===
factory = PiGPIOFactory()
servo = Servo(SERVO_PIN, pin_factory=factory, min_pulse_width=0.0005, max_pulse_width=0.0025)

# === Servo control functions ===
def servo_up():
    servo.value = 0.5
    print("Servo up")
    time.sleep(DELAY)

def servo_down():
    servo.value = -0.1
    print("Servo down")
    time.sleep(DELAY)

def servo_neutral():
    servo.value = 0
    print("Servo neutral")
    time.sleep(DELAY)

# === Test loop ===
try:
    while True:
        servo_up()
        #servo_down()
        #servo_neutral()

except KeyboardInterrupt:
    print("Exiting...")

finally:
    # === Stop the pigpio daemon ===
    subprocess.run(["sudo", "killall", "pigpiod"])
