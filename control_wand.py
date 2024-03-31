# usage: python3 led_temp.py [mac]
from __future__ import print_function
from mbientlab.metawear import MetaWear, libmetawear, parse_value
from mbientlab.metawear.cbindings import *
from time import sleep
import datetime
from threading import Event
import sys


class State:
    # init
    def __init__(self, device, name, signal=None):
        self.device = device
        self.name = name
        self.signal = signal
        self.mustRumble = True
        self.samples = 0
        self.lastValue = 0
        self.callback = FnVoid_VoidP_DataP(self.data_handler)
    def set_signal(self, signal):
        self.signal = signal

    # callback
    def data_handler(self, ctx, data):
        if ctx is None:
            ctx = datetime.datetime.now()
        print("%s [%s]: %s -> %s" % (self.name, ctx, self.device.address, parse_value(data)))
        self.lastValue=parse_value(data)
        self.samples+= 1
        if self.name == 'Switch' and self.lastValue == 1 and self.mustRumble:
            print('Rumbling motor')
            rumbleMotor()
            # print('Sending IR code sample {}'.format(self.samples))
            # self.mustRumble = False
        if self.name == 'Button' and self.lastValue == 0 and self.mustRumble:
            print('Button pressed')
            print('Sending IR code sample {}'.format(self.samples))
            # sendIRcode()
            sendIRcode()
            self.mustRumble = False


    def executeAction(self, action, value):
        currentTime = datetime.datetime.now()
        print("%s [%s]: %s -> %s" % (self.name, currentTime, 'In execute action for', value))


# connect
device_mac = "FC:0B:09:F5:4E:A4"  # Replace with your MetaMotion sensor MAC address
device = MetaWear(device_mac)
device.connect()
print("Connected to " + device.address + " over " + ("USB" if device.usb.is_connected else "BLE"))
dictHistoryStates = {}
libmetawear.mbl_mw_settings_set_device_name(device.board, 'Wand of Samonac', 15)
sBat = State(device, 'BAT')
sSwitch = State(device, 'Switch')
sButton = State(device, 'Button')

libmetawear.mbl_mw_settings_enable_3V_regulator(device.board, 1)

def rumbleMotor(cycle=50.0, width=500):
    print('In rumbleMotor with cycle = {} and width = {}'.format(cycle, width))
    libmetawear.mbl_mw_haptic_start_motor(device.board, cycle, width)


def getFusionSensor():
    s = State(device, 'QUAT')
    libmetawear.mbl_mw_settings_set_connection_parameters(s.device.board, 7.5, 7.5, 0, 6000)
    sleep(1.5)
    # setup quaternion
    libmetawear.mbl_mw_sensor_fusion_set_mode(s.device.board, SensorFusionMode.NDOF)
    libmetawear.mbl_mw_sensor_fusion_set_acc_range(s.device.board, SensorFusionAccRange._8G)
    libmetawear.mbl_mw_sensor_fusion_set_gyro_range(s.device.board, SensorFusionGyroRange._2000DPS)
    libmetawear.mbl_mw_sensor_fusion_write_config(s.device.board)
    # get quat signal and subscribe
    signal = libmetawear.mbl_mw_sensor_fusion_get_data_signal(s.device.board, SensorFusionData.QUATERNION)
    libmetawear.mbl_mw_datasignal_subscribe(signal, None, s.callback)
    # start acc, gyro, mag
    libmetawear.mbl_mw_sensor_fusion_enable_data(s.device.board, SensorFusionData.QUATERNION)
    libmetawear.mbl_mw_sensor_fusion_start(s.device.board)

    # sleep
    sleep(10.0)

    # tear down
    # stop
    libmetawear.mbl_mw_sensor_fusion_stop(s.device.board)
    sleep(1.0)
    # unsubscribe to signal
    signal = libmetawear.mbl_mw_sensor_fusion_get_data_signal(s.device.board, SensorFusionData.QUATERNION)
    sleep(1.0)
    libmetawear.mbl_mw_datasignal_unsubscribe(signal)
    sleep(1.0)
    # # disconnect
    # libmetawear.mbl_mw_debug_disconnect(s.device.board)
    # sleep(1.0)

    # recap
    print("Total Samples Received")
    print("%s -> %d" % (s.device.address, s.samples))


def parseSignalValue(state):
    lastValueStr = '{}'.format(state.lastValue)
    output = lastValueStr
    if state.name == 'BAT': # {voltage : 3637, charge : 10}
        output = output.replace('{', '')
        output = output.replace('}', '')
        [voltStr, chargeStr] = output.split(', ')
        voltStr = int(voltStr.split(' : ')[1])
        chargeStr = int(chargeStr.split(' : ')[1])
        output = {'voltage': voltStr, 'charge': chargeStr}

    if state.name=='Switch': # 0 or 1
        if output == '0':
            output = 'Released'
        else: output = 'Pressed'
    if state.name=='Button': # 0 or 1
        if output == '1':
            output = 'Released'
        else: output = 'Pressed'
    outputType = type(output)
    return {'data': output, 'type': outputType}


def getBatteryValue():
    print('Getting battery level')
    # Get battery level

    sBat.signal = libmetawear.mbl_mw_settings_get_battery_state_data_signal(device.board)
    libmetawear.mbl_mw_datasignal_subscribe(sBat.signal, None, sBat.callback)
    libmetawear.mbl_mw_datasignal_read(sBat.signal)
    sleep(0.5)
    dictHistoryStates['BAT'] = parseSignalValue(sBat)
    libmetawear.mbl_mw_datasignal_unsubscribe(sBat.signal)
    return


def getSwitchData(timeDelta=30):
    print('In getSwitchData()')
    # start acc, gyro, mag
    # libmetawear.mbl_mw_sensor_fusion_enable_data(s.device.board, SensorFusionData.QUATERNION)
    # libmetawear.mbl_mw_sensor_fusion_start(s.device.board)

    # sleep
    sleep(1.0)

    # Get onboard switch state
    # switch = libmetawear.mbl_mw_switch_get_state_data_signal(device.board)
    sSwitch.set_signal(libmetawear.mbl_mw_switch_get_state_data_signal(device.board))
    libmetawear.mbl_mw_datasignal_subscribe(sSwitch.signal, None, sSwitch.callback)
    # sleep(3.0)


    # auto
    libmetawear.mbl_mw_gpio_set_pull_mode(device.board, 1, GpioPullMode.UP)
    libmetawear.mbl_mw_gpio_set_pin_change_type(device.board, 1, GpioPinChangeType.ANY)
    sButton.set_signal(libmetawear.mbl_mw_gpio_get_pin_monitor_data_signal(device.board, 1))
    libmetawear.mbl_mw_datasignal_subscribe(sButton.signal, None, sButton.callback)

    # // Send notifications when the state changes
    libmetawear.mbl_mw_gpio_start_pin_monitoring(device.board, 1)

    sleep(1.0)
    print('Start playing with buttons')
    # Tests :

    # parameters = GpioAnalogReadParameters(pullup_pin=1, pulldown_pin=2, virtual_pin=0x15, delay_us=0)
    # an_signal = libmetawear.mbl_mw_gpio_get_analog_input_data_signal(board, 2, GpioAnalogReadMode.ADC)
    # libmetawear.mbl_mw_datasignal_read_with_parameters(an_signal, byref(parameters))



    # libmetawear.mbl_mw_gpio_set_pull_mode(device.board, 1, GpioPullMode.DOWN)
    # libmetawear.mbl_mw_gpio_set_pin_change_type(device.board, 1, GpioPinChangeType.ANY)
    #
    # pin_monitor_signal = libmetawear.mbl_mw_gpio_get_pin_monitor_data_signal(device.board, 1)
    # libmetawear.mbl_mw_datasignal_subscribe(pin_monitor_signal, None, s.callback)

    # libmetawear.mbl_mw_datasignal_read(pin_monitor_signal)


    # an_signal = libmetawear.mbl_mw_gpio_get_analog_input_data_signal(s.device.board, 1, GpioAnalogReadMode.ABS_REF)
    # libmetawear.mbl_mw_datasignal_subscribe(an_signal, None, s.callback)
    # libmetawear.mbl_mw_datasignal_read(an_signal)


    # di_signal = libmetawear.mbl_mw_gpio_get_digital_input_data_signal(device.board, 1)
    # libmetawear.mbl_mw_datasignal_subscribe(di_signal, None, s.callback)
    # libmetawear.mbl_mw_datasignal_read(di_signal)
    print('{} seconds left'.format(timeDelta))
    sleep(timeDelta)
    # print('10 seconds left')
    # sleep(10.0)
    print('done with both switch')
    # libmetawear.mbl_mw_datasignal_unsubscribe(pin_monitor_signal)
    # libmetawear.mbl_mw_datasignal_unsubscribe(an_signal)
    # libmetawear.mbl_mw_datasignal_unsubscribe(di_signal)

def unsubscribe():
    print('Unsubscribing')
    libmetawear.mbl_mw_datasignal_unsubscribe(sSwitch.signal)
    libmetawear.mbl_mw_datasignal_unsubscribe(sButton.signal)
    libmetawear.mbl_mw_gpio_stop_pin_monitoring(device.board, 1)
    libmetawear.mbl_mw_gpio_clear_digital_output(device.board, 0)
    sleep(3)

    print('done unsubscribing')

def sendIRcode(code=''):
    indexTemp = 0
    while indexTemp < 60:
        indexTemp += 1
        libmetawear.mbl_mw_gpio_set_digital_output(device.board, 0)
        # sleep(0.0001 * float(indexTemp))
        if indexTemp == 33 or indexTemp == 55:
            sleep(0.03)
        else:
            sleep(0.01)
        # print('indexTemp : ', indexTemp)
        libmetawear.mbl_mw_gpio_clear_digital_output(device.board, 0)
        sleep(0.01)


print('Starting')
getBatteryValue()
print("dictHistoryStates['BAT'] = {} of type {}".format(dictHistoryStates['BAT'], type(dictHistoryStates['BAT'])))

rumbleMotor()
# create led pattern
currentCharge = dictHistoryStates['BAT']['data']['charge']
if currentCharge >= 75:
    print('Battery Great')
    patternB = LedPattern(repeat_count= Const.LED_REPEAT_INDEFINITELY, high_intensity=int(31.0*currentCharge/100.0), rise_time_ms=200, fall_time_ms=200, pulse_duration_ms=500)
    libmetawear.mbl_mw_led_write_pattern(device.board, byref(patternB), LedColor.BLUE)
elif currentCharge < 10:
    print('Battery Really Low')
    patternR = LedPattern(repeat_count=Const.LED_REPEAT_INDEFINITELY,
                          high_intensity=int(31 - currentCharge), rise_time_ms=200,
                          fall_time_ms=100, pulse_duration_ms=500)

    libmetawear.mbl_mw_led_write_pattern(device.board, byref(patternR), LedColor.RED)
    rumbleMotor(cycle=10.0*(10-currentCharge), width=100*currentCharge)
elif currentCharge <= 20:
    print('Battery Low')
    patternR = LedPattern(repeat_count= Const.LED_REPEAT_INDEFINITELY, high_intensity=int(31-currentCharge), rise_time_ms=200, fall_time_ms=100, pulse_duration_ms=500)
    rumbleMotor(cycle=25, width=600)
else:
    print('Battery OK')
    patternG = LedPattern(repeat_count= Const.LED_REPEAT_INDEFINITELY, high_intensity=int(31.0*(currentCharge-20.0)/55.0), rise_time_ms=100, fall_time_ms=200, pulse_duration_ms=500)

    libmetawear.mbl_mw_led_write_pattern(device.board, byref(patternG), LedColor.GREEN)

libmetawear.mbl_mw_led_load_preset_pattern(byref(patternR), LedPreset.SOLID)

# play the pattern
libmetawear.mbl_mw_led_play(device.board)

# wait 5s
sleep(3.0)

# remove the led pattern and stop playing
libmetawear.mbl_mw_led_stop_and_clear(device.board)
sleep(1.0)

# print('Get fusion data:')
# getFusionSensor()
print('Get both switch data')
getSwitchData()

dictHistoryStates['Switch'] = parseSignalValue(sSwitch)
dictHistoryStates['Button'] = parseSignalValue(sButton)

print("Done")
unsubscribe()

libmetawear.mbl_mw_settings_enable_3V_regulator(device.board, 0)

print("dictHistoryStates['Switch'] = {} of type {}".format(dictHistoryStates['Switch'], type(dictHistoryStates['Switch'])))
print("dictHistoryStates['Button'] = {} of type {}".format(dictHistoryStates['Button'], type(dictHistoryStates['Button'])))

# play the pattern
libmetawear.mbl_mw_led_play(device.board)

rumbleMotor()
# wait 5s
sleep(1.0)

rumbleMotor(cycle=0.0, width=100)
# remove the led pattern and stop playing
libmetawear.mbl_mw_led_stop_and_clear(device.board)
sleep(1.0)

# disconnect
try:
    device.disconnect()
    print('disconnected')
except RuntimeError as err:
    print(err)
# finally:
#     print("Resetting device")
#
#     e = Event()
#     device.on_disconnect = lambda status: e.set()
#     print("Debug reset")
#     libmetawear.mbl_mw_debug_reset(device.board)
#     e.wait()
