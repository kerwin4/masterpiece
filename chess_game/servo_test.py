import pigpio
import time

SERVO_PIN = 17   # your pin

def main():
    pi = pigpio.pi()
    if not pi.connected:
        raise RuntimeError("pigpiod broken")
    while True:
        print("up (1000us)")
        pi.set_servo_pulsewidth(SERVO_PIN, 1000)
        time.sleep(1)
        '''
        print("Left (1000us)")
        pi.set_servo_pulsewidth(SERVO_PIN,700)
        time.sleep(1)
        '''
        print("Down (1900us)")
        pi.set_servo_pulsewidth(SERVO_PIN, 1900)
        time.sleep(1)
        

        print("Off")
        pi.set_servo_pulsewidth(SERVO_PIN, 0)
    pi.stop()

if __name__ == "__main__":
    main()
