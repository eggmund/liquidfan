#!/bin/python

from liquidctl import find_liquidctl_devices
import time
import os
import logging
import signal
import sys

UPDATE_PERIOD = 3

# List of points on fan curve
# (temperature, fan percentage)
# Maximum allowable temperature imo is 60 degrees for the liquid temperature.
FAN_CONFIGS = [
    [(25, 30), (30, 50), (40, 80), (60, 100)], # [(20, 40), (30, 40), (30, 60), (60, 100)],        # CPU Radiator fan2
    [(25, 0), (30, 50), (40, 80), (60, 100)] # Top fans
]
MIN_SPEED = 20

# Utility
FAN_CONFIG_NAMES = ["CPU Radiator fan", "Top fans"]
assert len(FAN_CONFIG_NAMES) == len(FAN_CONFIGS)

LOG_FILE_LOC = None # os.path.relpath("/var/log/liquidfan.log")

PWM_ROOT_FOLDER = r"/sys/devices/platform/it87.2624/hwmon/"
PWM_FILE_NAMES = ["pwm2", "pwm3"]

def get_pwm_folder(root_folder=PWM_ROOT_FOLDER):
    files = os.listdir(root_folder)
    return os.path.join(root_folder, files[0])

PWM_FOLDER = get_pwm_folder()


def write_manual_control_bit(pwm_file_name, bit_value, pwm_folder=PWM_FOLDER):
    with open(os.path.join(pwm_folder, pwm_file_name+"_enable"), "w") as enable_file:
        enable_file.write(str(bit_value))

    logging.info("Set manual control bit to '1' for %s", pwm_file_name)

# Returns the speed as a value between 0 and 1
def get_speed_from_curve(T, fan_config):
    # Linear interpolation between points
    # First of all find the bracket that we fall into
    lower_temp = 0
    lower_speed = 0

    upper_temp = None
    upper_speed = None

    for temp, speed in fan_config:
        upper_temp = temp
        upper_speed = speed
        if temp > T:
            break
        lower_temp = temp
        lower_speed = speed

    if upper_temp <= lower_temp:    # If at maximum temperature, return the last speed
        return upper_speed/100

    # Get equation for line
    # dy/dx
    m = (upper_speed - lower_speed)/(upper_temp - lower_temp)
    # c = y - mx
    c = upper_speed - m * upper_temp

    # y = mx + c
    speed = m * T + c
    if speed < MIN_SPEED:
        return MIN_SPEED/100

    return speed/100
    

# Updates the pwm file with the value
def set_fan_speed_from_temp(T, last, fan_config, pwm_file_loc):
    speed = int(get_speed_from_curve(T, fan_config) * 255)
    needs_update = speed != last

    if needs_update:   # If speed has changed
        # Note that fan speed is set from 0 to 255 in the sys file
        with open(pwm_file_loc, "w") as pwm_file:
            write_string = "%d" % speed
            pwm_file.write(write_string)

    return speed, needs_update


# Clean up when exiting
def on_exit(sig, frame):
    logging.debug("RECIEVED SIGNAL: '%s', exiting.", sig)
    for fan_name in PWM_FILE_NAMES:
        write_manual_control_bit(fan_name, 0)

    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, on_exit)
    signal.signal(signal.SIGTERM, on_exit)
    signal.signal(signal.SIGQUIT, on_exit)

    logging.basicConfig(filename=LOG_FILE_LOC, encoding='utf-8', level=logging.DEBUG)

    # Enable manual control for each fan
    for fan_name in PWM_FILE_NAMES:
        write_manual_control_bit(fan_name, 1)

    nzxt_device = None

    for dev in find_liquidctl_devices():
        if nzxt_device:
            break

        # connect to the device (here a context manager is used, but the
        # connection can also be manually managed)
        with dev.connect():
            if "NZXT Kraken" in dev.description:
                logging.info("FOUND KRAKEN")
                nzxt_device = dev


    with nzxt_device.connect() as con:
        init_status = con.initialize()
        logging.debug("Init status: %s", init_status)

        last_values = [None for _i in range(len(FAN_CONFIGS))]

        while True:
            status = con.get_status()
            logging.debug("Status: %s", status)
            
            # get liquid temperature in degrees C
            liq_temp = status[0][1]
            logging.debug("Liquid temperature: %.1f", liq_temp)

            # update fans
            for i in range(len(FAN_CONFIGS)):
                last_values[i], needed_update = set_fan_speed_from_temp(liq_temp, last_values[i], FAN_CONFIGS[i], os.path.join(PWM_FOLDER, PWM_FILE_NAMES[i]))

                if needed_update:
                    logging.info("Updating fan speed for fan header index: %d: %d", i, last_values[i])

            time.sleep(UPDATE_PERIOD)
