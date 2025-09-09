from Wiener import Wiener
import click, logging
from utils import verbosity, LoggingFormat
logger = logging.getLogger("WienerCLI")
"""

"""
@click.group(chain = True) # may need to add chain=True
@click.option('-d', "--device",
              default='LV',
              help = "HV or LV",
              type = click.STRING
              )
@click.option('-i', "--ip",
              default='10.179.59.29',
              type=click.STRING,
              help="IP address assigned to Wiener crate controller. Default: 10.179.59.29")
@click.option('-M', "--mib-path",
              default="/usr/share/snmp/mibs",
              help="Path to MIB files (e.g. path to WIENER-CRATE-MIB). Default: /usr/share/snmp/mibs ",
              type = click.Path(
                  exists=True,
                  file_okay=False,
                  readable=True)
              )
@click.option('-m', "--mib-name",
              default="WIENER-CRATE-MIB",
              help = "Name of Wiener Crate MIB file. Default: WIENER-CRATE-MIB ",
              type = click.STRING
              )
@click.option('-v', "--verbose", 
              count=True, 
              help = "Verbose output (-v = INFO, -vv = DEBUG)"
              )
@click.pass_context
def wicc(ctx, device, ip, mib_path, mib_name, verbose):
    ctx.obj = Wiener(host=ip, mib_dir=mib_path, mib_name=mib_name,device=device)
    ctx.device = device
    logger.level = verbosity(verbose)

    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(LoggingFormat())
    logger.addHandler(ch)
    
@wicc.command("channel")
@click.argument("channel", metavar="[CHANNEL]",type=click.INT, required=True, default=1)
@click.pass_obj
def cli_channel(obj, channel : int):
    obj.channel = channel

@wicc.command("set", help = ("Set VOLTAGE (V) and CURRENT (I) for channel"))
@click.argument("voltage", metavar="[VOLTAGE]", type=click.FLOAT, required=False, default=None)
@click.argument("current", metavar="[CURRENT]", required=False, default=None)
@click.pass_obj
def cli_set(obj, voltage : float | int , current : float | int):
    """
    Set VOLTAGE (V) and CURRENT (A) for channel output. "
    """
    v_set, i_set = obj.set_output(obj.channel, voltage, current)
    print(f"CH{obj.channel}: {i_set:.2f} mA, {v_set:.2f} V")
    return f"CH{obj.channel}: {i_set:.2f} mA, {v_set:.2f} V"

@wicc.command("enable")
@click.argument("state", required = True, default = 0)
@click.pass_obj
def cli_enable(obj, state : int | bool | str):
    """
    Enable or disable channel output.
    """
    state = 1 if state in ['on', 'ON', True, 1] else 0
    retv = obj.enable_output(obj.channel, state)
    print(f"{retv=}")
    return retv

@wicc.command("get-current")
@click.pass_obj
def cli_get_current(obj):
    """
    Read current setpoint in mA.
    """
    retv = obj.get_current(obj.channel)
    print(f"{retv} mA")
    return retv

@wicc.command("get-voltage")
@click.pass_obj
def cli_get_current(obj):
    """
    Read voltage setpoint in V.
    """
    retv = obj.get_voltage(obj.channel)
    print(f"{retv:.2f} V")
    return retv

@wicc.command("meas-current")
@click.pass_obj
def cli_meas_current(obj):
    """
    Read measured terminal current in mA. 
    """
    retv = obj.meas_current(obj.channel)
    print(f"{retv} mA")
    return retv

@wicc.command("meas-voltage")
@click.pass_obj
def cli_meas_voltage(obj):
    """
    Read measured terminal voltage in V.
    """
    retv = obj.meas_term_voltage(obj.channel)
    print(f"{retv:.2f} V")
    return retv

if __name__=='__main__':
    wicc()