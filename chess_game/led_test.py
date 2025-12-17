import pigpio
import time
from subprocess import Popen, PIPE

def start_pigpio_daemon():
    """
    starts the pigpio daemon if it's not already running

    Returns:
        None
    """
    p = Popen("sudo pigpiod", stdout=PIPE, stderr=PIPE, shell=True)
    s_out, s_err = p.communicate()  # use communicate to wait for process and get output

    if not s_out and not s_err:
        print("pigpiod started")
    elif b"pigpio.pid" in s_err:
        print("pigpiod already running")
    else:
        print(f"error pigpiod {s_err.decode()}")

def stop_pigpio_daemon():
    """
    stops the pigpio daemon if it's running

    Returns:
        None
    """
    # attempt to stop gracefully
    p = Popen("sudo killall pigpiod", stdout=PIPE, stderr=PIPE, shell=True)
    _, s_err = p.communicate()

    # check to see what happened
    if p.returncode == 0:
        print("pigpiod stopped")
    elif p.returncode == 1:
        print("pigpiod was not running")
    else:
        print(f"error stopping pigpiod: {s_err.decode()}")

# GPIO pins
WHITE_LED_PIN = 27
BLACK_LED_PIN = 22

start_pigpio_daemon()

# Connect to pigpio daemon
pi = pigpio.pi()
if not pi.connected:
    exit("Failed to connect to pigpio daemon.")

# Functions to control LEDs
def white_led_on():
    pi.write(WHITE_LED_PIN, 1)

def white_led_off():
    pi.write(WHITE_LED_PIN, 0)

def black_led_on():
    pi.write(BLACK_LED_PIN, 1)

def black_led_off():
    pi.write(BLACK_LED_PIN, 0)

# Example usage
white_led_on()
time.sleep(1)
white_led_off()

black_led_on()
time.sleep(1)
black_led_off()

# Example usage
white_led_on()
time.sleep(1)
white_led_off()

black_led_on()
time.sleep(1)
black_led_off()

# Example usage
white_led_on()
time.sleep(1)
white_led_off()

black_led_on()
time.sleep(1)
black_led_off()

# Example usage
white_led_on()
time.sleep(1)
white_led_off()

black_led_on()
time.sleep(1)
black_led_off()

# Cleanup
pi.stop()
stop_pigpio_daemon()