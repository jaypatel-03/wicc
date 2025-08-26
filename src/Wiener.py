import asyncio, time
from pysnmp.hlapi.v3arch.asyncio import *
from utils import FloatOpaque, opaque_to_float, switch_to_int, LoggingFormat
from functools import wraps

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
    def __init__(self, host: str, mib_dir: str, mib_name: str, device : str):
        self.authData_public = CommunityData('public', mpModel=1)  # v2c
        self.authData_guru = CommunityData('guru', mpModel=1)  # v2c
        
        # self._target = UdpTransportTarget.create((host, 161))
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
        offset = 99 if self.device == "HV" else -1
        if channel == 64 or channel == 128: # special channels for group TODO: better way to do that?
            return channel
        mapped_channel = channel + offset
        mapped_channel_id = f'u{str(mapped_channel)}' 
        return mapped_channel_id

        
    def snmp_call(auth : str, snmp_func):
        """
        Decorator to send SNMP request (snmp_func = get/set) to the Wiener crate, with authority 'public' 
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
        

    def set_voltage(self, channel: int, voltage: float):
        """
        Set the voltage on the device.
        """
        logger.debug(f"Setting output voltage of CH{channel} to {voltage} V ")
        rval = asyncio.run(self.write('outputVoltage', channel, voltage))
        return opaque_to_float(rval)
    
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
        """"""
        logger.debug(f"Reading measured output current of CH{channel}")
        raw = asyncio.run(self.read("outputMeasurementCurrent", channel))
        return opaque_to_float(raw)

    def set_output(self, channel : int, voltage : float, current :float):
        logger.debug(f"Setting CH{channel} to {voltage} V and {current} A")
        v_set = self.set_voltage(channel, voltage)
        i_set = self.set_current(channel, current)
        return v_set, i_set

    def output_enabled(self, channel : str):
        logger.debug(f"Reading whether CH{channel} is on/off")
        raw = asyncio.run(self.read("outputSwitch", channel))
        if "on" in str(raw):
            return True
        return False

    def enable_output(self, channel : str, state : int | str | bool):
        """Accepts states 0 (off), 1 (on) """
        logger.debug(f"Turning CH{channel} to {state}")
        raw = asyncio.run(self.write("outputSwitch", channel, switch_to_int(state)))
        return raw

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

def main():
    wiener = Wiener(host='10.179.59.29', mib_dir='/usr/share/snmp/mibs', mib_name='WIENER-CRATE-MIB', device ='LV')
    
    print(wiener.set_current(channel = 1, current= 0.5))
    
    # print(wiener.set_voltage(channel=2, voltage=100.0))
    # time.sleep(1)
    # print(wiener.get_voltage(2))
    # print(wiener.enable_output(2, 'on'))
    # print(wiener.get_voltage(channel=2))
    # print(wiener.identify)
    # time.sleep(2)
    # wiener.set_voltage(50.0', channel='u101')
    # print(wiener.all_off())
    # time.sleep(2)
    # print(wiener.get_voltage(channel='u101'))
    
if __name__ == '__main__':
    main()