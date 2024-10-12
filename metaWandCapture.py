# usage: python3 led_temp.py [mac]
from __future__ import print_function
from mbientlab.metawear import MetaWear, libmetawear
from mbientlab.metawear.cbindings import *
from time import sleep
from threading import Event
# import mbientlab.metawear.module.Gpio.Pullmode


from mbientlab.metawear.cbindings import Module
# Module.GPIO
from mbientlab.metawear.cbindings import GpioPinChangeType, GpioPullMode, \
    GpioAnalogReadParameters, GpioAnalogReadMode
# from pymetawear.modules.base import PyMetaWearModule, data_handler

import sys

# connect
#device = MetaWear(sys.argv[1])
device = MetaWear('FC:0B:09:F5:4E:A4')
device.connect()
print("Connected to " + device.address + " over " + ("USB" if device.usb.is_connected else "BLE"))

def ledPatterns():
    # create led pattern
    pattern= LedPattern(repeat_count= Const.LED_REPEAT_INDEFINITELY)
    libmetawear.mbl_mw_led_load_preset_pattern(byref(pattern), LedPreset.BLINK)
    libmetawear.mbl_mw_led_write_pattern(device.board, byref(pattern), LedColor.GREEN)
    # libmetawear.mbl_mw_i2c_write()
    libmetawear.mbl_mw_gpio_set_pull_mode(device.board, 1, GpioPullMode.UP)
    # libmetawear.mbl_mw_gpio_set_pull_mode(device.board, 0, GpioPullMode.UP)
 	# Sets the pin pull mode. More...
    libmetawear.mbl_mw_gpio_set_digital_output(device.board, 1)
    # libmetawear.mbl_mw_gpio_set_digital_output(device.board, 0)
    sleep(3)
    libmetawear.mbl_mw_gpio_clear_digital_output(device.board, 1)
    # libmetawear.mbl_mw_gpio_clear_digital_output(device.board, DOWN)

    sleep(3)
    
    libmetawear.mbl_mw_gpio_set_pull_mode(device.board, 1, GpioPullMode.DOWN)
    
    
    # play the pattern
    libmetawear.mbl_mw_led_play(device.board)
    sleep(1)
    libmetawear.mbl_mw_haptic_start_motor(device.board, 30.0, 5000)
    sleep(1)

    libmetawear.mbl_mw_led_stop_and_clear(device.board)

    libmetawear.mbl_mw_haptic_start_motor(device.board, 0.0, 100)
    libmetawear.mbl_mw_led_write_pattern(device.board, byref(pattern), LedColor.GREEN)
    sleep(1)
    libmetawear.mbl_mw_haptic_start_motor(device.board, 70.0, 1000)

    # play the pattern
    libmetawear.mbl_mw_led_play(device.board)

    sleep(1)

    libmetawear.mbl_mw_led_stop_and_clear(device.board)

    libmetawear.mbl_mw_haptic_start_motor(device.board, 0.0, 100)
    libmetawear.mbl_mw_led_write_pattern(device.board, byref(pattern), LedColor.RED)

    libmetawear.mbl_mw_haptic_start_motor(device.board, 90.0, 300)

    # play the pattern
    libmetawear.mbl_mw_led_play(device.board)
    sleep(1)

    libmetawear.mbl_mw_led_stop_and_clear(device.board)

    libmetawear.mbl_mw_haptic_start_motor(device.board, 35.0, 700)

    libmetawear.mbl_mw_led_write_pattern(device.board, byref(pattern), LedColor.BLUE)

    # libmetawear.mbl_mw_led_write_pattern(device.board, byref(pattern), LedColor.WHITE)


    # play the pattern
    libmetawear.mbl_mw_led_play(device.board)

    # wait 5s
    sleep(5.0)


    # remove the led pattern and stop playing
    libmetawear.mbl_mw_led_stop_and_clear(device.board)
    sleep(2.0)

try:
    index = -1
    while index < 33:
        index+=1
        print('index = ', index)
        ledPatterns()
        sleep(5)

    
    device.disconnect()
    sleep(1.0)


except KeyboardInterrupt:
    print("Done")
    # disconnect
    device.disconnect()
    sleep(1.0)
