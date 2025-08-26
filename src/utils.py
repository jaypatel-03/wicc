import struct, logging
from pysnmp.proto.rfc1902 import Opaque
import click
from functools import update_wrapper

def strip_hex(s : str) -> int:
    s_strip = s[2:] if s[0:2] == "0x" else s #remove hex prefix
    s_strip = s_strip[2:] if s_strip[0:2] == "44" else s_strip

    if s_strip[0:2] == "9f":  #remove BER type tag (9f79 : DOUBLETYPE, 9f78 : FLOAT)
        n_bits = int(s_strip[4:7], 16)
        s_strip = s_strip[6:]
    else:
        n_bits = len(s_strip) - 1
    return s_strip

def hex_to_bin(n : str | int) -> int:
    n = hex(n) if isinstance(n,int) else n
    if n[0:2] == "0x" or n[0:2] == "9f":
        n = strip_hex(n)
    return f"{int(n,16):0>32b}" # f'{number:{pad}{rjust}{size}{kind}}'

def calc_mantissa(n : str) -> int:
    m = 1
    for i, n_bit in enumerate(n):
        m = m + 2**-(i+1) if bool(int(n_bit,2)) else m
    return m

def bin_to_dec(n : str) -> int:
    assert len(n) == 32, "Not 32-bit floating-point"
    # print(len(n))
    sign = 1 if bool(n[0]) else -1
    
    _exp = int(n[1:9],2) - 127
    exp = _exp if _exp > -127 else -126

    mantissa = calc_mantissa(n[9:])
    dec = sign * 2**exp * mantissa
    return dec

def decode_ber(ser : str | int, prec : int = 4) -> float:
    """ Decodes output of SNMP commands from BER ASN.1 type encoding (IEEE 754) to decimal, with appropriate truncation to account for floating-point precision.

    For example, the BER serialization of value 123 of type DOUBLETYPE is '9f7908405ec00000000000'h.
        (The tag is '9f79'h; the length is '08'h; and the value is '405ec00000000000'h.)  
    The BER serialization of value '9f7908405ec00000000000'h of data type Opaque is '440b9f7908405ec00000000000'h.  
        (The tag is '44'h; the length is '07'h; and the value is '9f7908405ec00000000000'h.)"
    """
    ser = hex(ser) if isinstance(ser, int) else ser
    assert len(ser) == 16, "Not BER or hex"

    _bin = hex_to_bin(ser)
    dec = bin_to_dec(_bin)
    #truncates to the appropriate precision for floating point
    x = 10 ** prec 
    trunc_dec = int(dec * x)/x
    return trunc_dec

class FloatOpaque(Opaque):
    """
    Encodes a 32-bit IEEE754 float as the WIENER FLOATTYPE tag-length-value (TLV) format.:
        0x9f 0x78 0x04 <4-byte big-endian float>
    Pass *only* the FLOATTYPE TLV bytes to the Opaque constructor — pysnmp will add the outer Opaque wrapper itself.
    """
    def __init__(self, value):
        float_bytes = struct.pack(">f", float(value)) #
        float_type_tlv = b'\x9f\x78\x04' + float_bytes #prepends tags
        super().__init__(float_type_tlv)  # Opaque(inner_tlv)

def opaque_to_float(o: Opaque) -> float:
    """
    Decode the Wiener FLOATTYPE inside of an Opaque object.
    Returns Python float. Raises ValueError on unexpected formats.
    """
    payload = bytes(o.asNumbers()) if hasattr(o, 'asNumbers') else bytes(o) 
    # payload is the inner bytes (prefixes 0x9f 0x78 0x04 are tags indicating type 0x9f78 
    # and length of data 0x04). 
    if len(payload) < 6 or payload[0:2] != b'\x9f\x78' or payload[2] != 0x04:
        raise ValueError(f"Not a Wiener FLOATTYPE value: {payload!r}")
    float_bytes = payload[3:7] # trim initial tags
    return struct.unpack(">f", float_bytes)[0]

def switch_to_int(state : str | int | bool) -> int:
    if isinstance(state,bool):
        return 1 if state else 0
    elif isinstance(state,str):
        return 1 if "on" in state.lower() else 0
    return state

def verbosity(level : int):
    if level == 0:
        return logging.WARNING
    elif level == 1:
        return logging.INFO
    else:
        return logging.DEBUG
    

class LoggingFormat(logging.Formatter):
    """
    Use ANSI colour codes to format logging messages
    """
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s @ (%(filename)s:%(lineno)d)"

    formats = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }
        
    def format(self, record):
        log_fmt = self.formats.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)