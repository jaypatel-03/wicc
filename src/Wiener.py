import asyncio

from pysnmp.hlapi.v3arch.asyncio import *
from utils import FloatOpaque, opaque_to_float, switch_to_int, LoggingFormat
from functools import wraps
import time
import logging
logger = logging.getLogger("WienerClass")


'''

# create console handler with a higher log level
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
console.setFormatter(LoggingFormat())
logger.addHandler(console)
'''


class Wiener:
    statusBits = { # dictionary taken from the WIENER-CRATE-MIB file defining the mapping between error bits and messages
    0 : "outputOn",
    1 : "outputInhibit" ,
    2 : "outputFailureMinSenseVoltage",
    3 : "outputFailureMaxSenseVoltage",
    4 : "outputFailureMaxTerminalVoltage",
    5 : "outputFailureMaxCurrent",
    6 : "outputFailureMaxTemperature",
    7 : "outputFailureMaxPower",
    8 : "reserved",
    9 : "outputFailureTimeout",
    10 : "outputCurrentLimited",
    11 : "outputRampUp",
    12 : "outputRampDown",
    13 : "outputEnableKill",
    14 : "outputEmergencyOff",
    15 : "outputAdjusting",
    16 : "outputConstantVoltage",
    17 : "outputLowCurrentRange",
    18 : "outputCurrentBoundsExceeded",
    19 : "outputFailureCurrentLimit",
    20 : "outputCurrentIncreasing",
    21 : "outputCurrentDecreasing",
    22 : "outputConstantPower",
    23 : "outputVoltageRampSpeedLimited",
    24 : "outputVoltageBottomReached",
    25 : "outputInitCrcCheckBad"
}
    def __init__(self, host: str, mib_dir: str, mib_name: str, device : str):
        self.authData_public = CommunityData('public', mpModel=1)  # v2c
        self.authData_guru = CommunityData('guru', mpModel=1)  # v2c
        
        self.host = host
        self._context = ContextData()
        self._mib_dir = mib_dir
        self._mib_name = mib_name
        self.device = device
    
    def cli_store_channel(self, channel : int):
        if 1 <= channel <= 8: 
            self.channel = channel
        else:
            raise ValueError("Channels range from 1 to 8")
        
    def get_channel(self, channel : int) -> str | int:
        """
        Translate channels 1-8 to the names defined by the Wiener Crate: 
        LV: Channels 1 - 8 are mapped to u0 - u7
        HV: Channels 1 - 8 are mapped to u100 - u107
        Channels 64 and 128 are used by the groupsSwitch function to apply actions to all HV and LV channels respectively 
        """
        offset = 99 if self.device == "HV" else -1
        if channel == 64 or channel == 128: # special channels for group TODO: better way to do that?
            return channel
        mapped_channel = channel + offset
        mapped_channel_id = f'u{str(mapped_channel)}' 
        return mapped_channel_id

        
    def snmp_call(auth : str, snmp_func):
        """
        Decorator to send SNMP request (snmp_func = get/set) to the Wiener crate, with given authority
        This translates the channel number before passing it
          
        """
        def _decorator(func):
            @wraps(func)
            async def wrapper(self,  command: str, channel: str, *args, **kwargs):
                channel = self.get_channel(channel) if isinstance(channel, int) else channel
                
                
                logger.debug(f"Sending {command}.{channel} to {self.device} Wiener module")
                target = await UdpTransportTarget.create((self.host, 161))
                oid = ObjectIdentity(self._mib_name, command, channel) \
                    .add_mib_source(self._mib_dir) \
                    .load_mibs(self._mib_name)
                
                rvals = await func(self, oid, *args, **kwargs)

                errorIndication, errorStatus, errorIndex, varBinds = await snmp_func(
                    SnmpEngine(),
                    getattr(self, f"authData_{auth}"),
                    target,
                    self._context,
                    *rvals
                )

                if errorIndication:
                    raise Exception(f"Error in {snmp_func.__name__} {command}: {errorIndication}")
                elif errorStatus:
                    raise Exception(f"Error status {errorStatus.prettyPrint()} at "
                                    f"{varBinds[int(errorIndex)-1][0] if errorIndex else '?'}")
                else:
                    return varBinds[0][1] if varBinds else None
            return wrapper
        return _decorator

    # SNMP get commands must be executed with authorisation 'public' 
    # i.e. snmpget -v 2c -M /usr/share/snmp/mibs -m +WIENER-CRATE-MIB -c public 10.179.59.29 outputVoltage.101
    @snmp_call("public", get_cmd)
    async def read(self, oid):
        return [ObjectType(oid)]

    # SNMP set commands must be executed with authorisation 'guru' 
    # i.e. snmpget -v 2c -M /usr/share/snmp/mibs -m +WIENER-CRATE-MIB -c public 10.179.59.29 outputVoltage.101 F 100.0
    @snmp_call("guru", set_cmd)
    async def write(self, oid, val : float | int):
        # floats must be encoded using BER ASN.1 FLOATTYPE, as defined in WIENER-CRATE-MIB.txt
        # integers are passed normally. 
        if isinstance(val, float):
            return [ObjectType(oid, FloatOpaque(val))]
        return [ObjectType(oid, val)]
        

    def set_voltage(self, channel: int, voltage: float, tries : int = 3):
        """
        Set the voltage on the device.
        """
        if voltage == 0.0:
            self.enable_output(channel, 0)
        elif isinstance(voltage, int):
            try:
                voltage=float(voltage)
            except:
                raise TypeError("Voltage setpoint cannot be cast to float")
        for i in range(tries):
            print(f"Try {i + 1}")
            logger.debug(f"Setting output voltage of CH{channel} to {voltage} V ")
            rval = asyncio.run(self.write('outputVoltage', channel, voltage))
            time.sleep(5)
            status = self.get_output_status(channel)
            print(status)
            if "outputLowCurrentRange" in status:
                print("Retry after first delay")
                self.clear_events(channel)
                continue
            
            delay = voltage/5 - 5 if voltage/5 > 5 else 1
            volt_meas = self.get_voltage(channel)
            status = self.get_output_status(channel)
            time.sleep(delay)
            if (voltage - 1 <= volt_meas <= voltage + 1) and ("outputConstantVoltage" in status): 
                return opaque_to_float(rval)
            print("Retry after second delay")
            self.clear_events(channel)
        return "Failed"
    
    def get_voltage(self, channel: int) -> float:
        """
        Get the voltage from the device.
        
        Returns:
            float: The current voltage.
        """
        logger.debug(f"Reading outputVoltage of CH{channel} ")
        raw = asyncio.run(self.read("outputVoltage", channel))
        return opaque_to_float(raw)
  
    def meas_term_voltage(self, channel: int):
        """"""
        logger.debug(f"Reading measured terminal voltage of CH{channel}")
        raw = asyncio.run(self.read("outputMeasurementTerminalVoltage", channel))
        return opaque_to_float(raw)
  
    def meas_sense_voltage(self, channel: int):
        logger.debug("Reading measured sense voltage of CH{channel}")
        raw = asyncio.run(self.read("outputMeasurementSenseVoltage", channel))
        return opaque_to_float(raw)
    
    def set_current(self, current: float, channel: int = None):
        """
        Set the current on the device.
        
        Args:
            current (float): The current to set.
        """
        logger.debug(f"Setting output current of CH{channel} to {current} V ")
        if isinstance(current, int):
            try:
                current = float(current)
            except:
                raise TypeError("Current could not be cast to float.")
        rval = asyncio.run(self.write('outputCurrent', channel, current))
        return opaque_to_float(rval)
    
    
    def get_current(self, channel: int) -> float:
        """
        Reads the current setpoint
        """
        logger.debug(f"Reading nominal output current of CH{channel}")
        raw = asyncio.run(self.read("outputCurrent", channel))
        return opaque_to_float(raw)

    def meas_current(self, channel: int):
        """
        Returns the current measured at the terminal
        """
        logger.debug(f"Reading measured output current of CH{channel}")
        raw = asyncio.run(self.read("outputMeasurementCurrent", channel))
        return opaque_to_float(raw)

    def set_output(self, channel : int, voltage : float, current :float):
        logger.debug(f"Setting CH{channel} to {voltage} V and {current} A")
        v_set = self.set_voltage(channel, voltage)
        i_set = self.set_current(channel, current)
        return v_set, i_set

    def output_enabled(self, channel : int):
        logger.debug(f"Reading whether CH{channel} is on/off")
        raw = asyncio.run(self.read("outputSwitch", channel))
        if "on" in str(raw):
            return True
        return False

    def enable_output(self, channel : int, state : int | str | bool, tries : int = 3):
        """Accepts states 0 (off), 1 (on).  
        
        """
        if state in ['off', 0, False, 'OFF']:
            logger.debug(f"Turning CH{channel} OFF")
            raw = asyncio.run(self.write("outputSwitch", channel, 0))
            return raw
        for i in range(tries):
            logger.debug(f"Turning CH{channel} to {state}: Attempt {i+1}")
            print(f"Try {i + 1}")
            raw = asyncio.run(self.write("outputSwitch", channel, 1))
            print("Ramping up...please wait")
            first_delay = 7
            time.sleep(first_delay)
            status = self.get_output_status(channel)
            print(status)
            if "outputLowCurrentRange" in status:
                print("Retry after first delay")
                self.clear_events(channel)
                continue
            elif "outputConstantVoltage" in status:
                return raw
            volt_meas = self.meas_term_voltage(channel)
            volt_set = self.get_voltage(channel)
            delay = volt_set/5 - first_delay if volt_set/5 > first_delay else 1
            status = self.get_output_status(channel)
            time.sleep(delay)
            if (volt_set - 1 <= volt_meas <= volt_set + 1) and ("outputConstantVoltage" in status): 
                return raw
            print("Retry after second delay")
            self.clear_events(channel)
            time.sleep(2)
        return "Failed"
    
    def all_off(self):
        logger.debug("Ramping down and turning off all channels")
        channel = 64 if self.device == "HV" else 128
        raw = asyncio.run(self.write("groupsSwitch", channel, 0))
        return raw
    
    def identify(self):
        logger.debug("Reading module description")
        channel = 'ma0' if self.device == "LV" else 'ma1'
        raw = asyncio.run(self.write("moduleDescription", channel))
        return raw

    def set_crate_power(self, state : int | str | bool):
        logger.debug(f"Set crate power to {state}")
        raw = asyncio.run(self.write("sysMainSwitch", 0, switch_to_int(state)))
        return raw
    
    def get_crate_power(self):
        logger.debug("Read crate power state")
        raw = asyncio.run(self.read("sysMainSwitch", 0))
        if "on" in str(raw):
            return True
        return False
    
    def get_output_status(self, channel : int):
        """
        Output status is output as a ASN BITS object which is a pain to interpret. 
        The function returns 3 hex numbers (0x__ 0x__ 0x__) which needs to be split up into substrings.
        Returns an array of status conditions 
        """
        logger.debug(f"Reading output status of CH{channel}")
        raw = asyncio.run(self.read("outputStatus", channel))
        bs = str(bytes(raw).hex())
        out = ""
        for i in range(int(len(bs)/2)):
            hx = int(bs[2*i:2*i+2], 16) # consider each 2-digit hex number in 
            out += f"{hx:>08b}" #translate to binary, pad to little-endian 8 bits 
        retv = []
        for i, bit in enumerate(out):
            # for each bit that is true (1), lookup the corresponding error code in the statusBits dictionary
            logging.debug(f"Bit {i} : {bit} = {self.statusBits.get(int(i)) if bit == '1' else ''}")
            retv.append(self.statusBits.get(int(i)) if bit == '1' else '') 
        return [a for a in retv if a != '']
    
    def clear_events(self, channel : int):
        logger.debug(f"Clearing events of CH{channel}")
        raw = asyncio.run(self.write("outputSwitch", channel, 10))
        return raw
     
    def clear_all_events(self):
        logger.debug(f"Clearing all events")
        channel = 64 if self.device == "HV" else 128
        raw = asyncio.run(self.write("groupsSwitch", channel, 10))
        return raw
    
def main():
    wiener = Wiener(host='10.179.59.29', mib_dir='/usr/share/snmp/mibs', mib_name='WIENER-CRATE-MIB', device ='HV')
    
    # print(wiener.get_output_status(channel = 1))
    # print(wiener.clear_events(2))
    
    # print(wiener.get_output_status(channel = 1))
    # print(wiener.get_output_status(channel = 3))
    # print(wiener.set_voltage(channel=1, voltage=30.0))
    # time.sleep(1)
    # print(wiener.get_voltage(2))
    print(wiener.enable_output(2, 'on'))
    # print(wiener.get_voltage(channel=2))
    # print(wiener.identify)
    # time.sleep(2)
    # wiener.set_voltage(50.0', channel='u101')
    # print(wiener.all_off())
    # time.sleep(2)
    # print(wiener.get_voltage(channel='u101'))
    
if __name__ == '__main__':
    main()