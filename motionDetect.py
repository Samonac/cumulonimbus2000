# Complete Project Details: https://RandomNerdTutorials.com/raspberry-pi-detect-motion-pir-python/

from gpiozero import MotionSensor
from signal import pause
import datetime

pir = MotionSensor(32)

def motion_function():
    print("\n\n <!> Motion Detected !")
    currentTime = datetime.datetime.now()
    currentTime = '{}'.format(currentTime).replace(' ', '_').replace(':', '-').replace('.', '_')
    print('currentTime : ', currentTime)

def no_motion_function():
    print("\n => Motion stopped")
    currentTime = datetime.datetime.now()
    currentTime = '{}'.format(currentTime).replace(' ', '_').replace(':', '-').replace('.', '_')
    print('currentTime : ', currentTime)

pir.when_motion = motion_function
pir.when_no_motion = no_motion_function

pause()