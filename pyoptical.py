#!/usr/bin/env python
#coding=utf-8

"""

pyoptical - a pure python interface to the CRS  OptiCal photometer.

@author valentin.haenel@gmx.de

Example:

import pyoptical
op = pyoptical.OptiCal('dev/dev/ttyUSB0')
op.read_luminance()

"""

import serial

ACK='\x06'
NACK='\x15'

def to_int(list_of_bytes):
    """ convert a list of bytes(in least significant byte order) to int """
    list_of_bytes.reverse()
    return int("".join(list_of_bytes).encode('hex'),16)

class OptiCalException(Exception):
    """ base exception for all OptiCal exceptions """

class NACKException(OptiCalException):
    """ is raised when the OptiCal sends a NACK byte """
    def __str__(self):
        return "OptiCal sent a NACK while trying to: %s" % self.message

class TimeoutException(OptiCalException):
    """ is raised when the OptiCal does not respond within the timeout limit """
    def __str__(self):
        return "OptiCal timeout while trying to: %s" % self.message

class OptiCal(object):
    """ object to access the OptiCal """
    def __init__(self, com_port, mode='current', debug=True, timeout=5):
        """ initialise OptiCal

            The constructor will obtain a reference to the device, do the
            initial calibration, read all ref parameters, and put the device
            into the requested mode.

            arguments:
                com_port:   name of the com_port
                mode:       mode of the OptiCal, either 'current' or 'voltage'
                timeout:    time in seconds to wait for a response

            instance variables:

            For more information consult the docstring of the pyoptical module,
            and the OptiCal Users Guide Version 4, available from the CRS
            website.

        """
        self.phot = serial.Serial(com_port, timeout=timeout)
        self._calibrate()
        self._read_ref_defs()
        if mode is 'current':
            self._set_current_mode()
        elif mode is 'voltage':
            self._set_voltage_mode()
        else:
            raise OptiCalException("Mode: '"+mode+"' is not supported by "\
                    +"OptiCal, either use 'current'(default) or 'voltage'")

    def _calibrate(self):
        self._send_command('C', "calibrate")

    def _set_current_mode(self):
        self.mode = 'current'
        self._send_command('I', "set current mode")

    def _set_voltage_mode(self):
        self.mode = 'voltage'
        self._send_command('V', "set voltage mode")

    def _send_command(self, command, description):
        self.phot.write(command)
        ret = self.phot.read()
        self._check_return(ret, description)

    def _check_return(self, ret, description):
        """ check the return value of a read """
        if ret == "":
           raise TimeoutException(description)
        if NACK in ret:
           raise NACKException(description)

    def _read_ref_defs(self):
        """ read all parameters with a ref definition """
        self.V_ref = to_int(self._read_eeprom(16,19))
        self.Z_count = to_int(self._read_eeprom(32,35))
        self.R_feed = to_int(self._read_eeprom(48,51))
        self.R_gain = to_int(self._read_eeprom(64,67))
        self.K_cal = to_int(self._read_eeprom(96,99))

    def _read_eeprom_single(self, address):
        """ read contents of eeprom at single address

            arguments:
                address: an integer in the range 0<i<100

            returns:
                a byte in the range 0<i<256 as str

            note: the ACK byte is removed for you
        """
        self.phot.write(chr(128+address))
        ret = self.phot.read(2)
        self._check_return(ret, "reading eeprom at address %d" % address)
        # if _check_return does not raise an excpetion
        return ret[0]

    def _read_eeprom(self, start, stop):
        """ read contents of eeprom between start and stop inclusive

            arguments:
                start: an integer in the range 0<i<100
                stop: and integer in the range 0<i<100

            returns:
                a list of bytes in the range 0<i<256 as str
        """
        ret = []
        for i in range(start, stop+1):
            ret.append(self._read_eeprom_single(i))
        return ret

    def _read_adc(self):
        """ read and correct the ADC value """
        self.phot.write('L')
        ret = self.phot.read(4)
        self._check_return(ret, "reading adc value")
        # truncate the NACK
        ret = ret[:-1]
        # obtain an integer value from the bytes
        adc = to_int([ret[0], ret[1], ret[2]])
        print "adc_mine", adc
        print ord(ret[0])+(ord(ret[1])<<8)+(ord(ret[2])<<16)
        return adc - self.Z_count - 524288

    def get_luminance(self):
        """ the luminance measured in cd/m**2 """
        if self.mode is not 'current':
            raise OptiCalException("get_luminance() is only available in 'current' mode")
        return self._get_measurement()

    def get_voltage(self):
        """ the measured voltage in V """
        if self.mode is not 'voltage':
            raise OptiCalException("get_voltage() is only available in 'voltage' mode")
        return self._get_measurement()

    def _get_measurement(self):
        ADC_adjust = self._read_adc()
        numerator =  (float((ADC_adjust)/524288.0) * self.V_ref * 1.e-6)
        if self.mode is 'current':
            denominator = self.R_feed * self.K_cal * 1.e-15
        return numerator / denominator

    def _read_product_type(self):
        return self._read_eeprom(0,1)

    def _read_optical_serial_number(self):
        return self._read_eeprom(2,5)

    def _read_firmware_version(self):
        return self._read_eeprom(6,7)

    def _read_probe_serial_number(self):
        return self._read_eeprom(80,95)

    def _read_ref_voltage(self):
        return self._read_eeprom(16,19)

    def _read_zero_error(self):
        return self._read_eeprom(32,35)

    def _read_feedback_resistor(self):
        return self._read_eeprom(48,51)

    def _read_voltage_gain_resistor(self):
        return self._read_eeprom(64,67)

    def _read_probe_calibration(self):
        return self._read_eeprom(96,99)
