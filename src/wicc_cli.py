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
              help="IP address assigned to Wiener crate controller")
@click.option('-M', "--mib-path",
              default="/usr/share/snmp/mibs",
              help="Path to MIB files (e.g. path to WIENER-CRATE-MIB)",
              type = click.Path(
                  exists=True,
                  file_okay=False,
                  readable=True)
              )
@click.option('-m', "--mib-name",
              default="WIENER-CRATE-MIB",
              help = "Name of Wiener Crate MIB file",
              type = click.STRING
              )
@click.option('-v', "--verbose", 
              count=True, 
              help = "Verbose output (-v = INFO, -vv = DEBUG)"
              )
@click.pass_context
def wicc(ctx, device, ip, mib_path, mib_name, verbose):
    ctx.obj = Wiener(host=ip, mib_dir=mib_path, mib_name=mib_name,device=device)
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
@click.argument("current", metavar="[CURRENT]", required=False, default=None)
@click.argument("voltage", metavar="[VOLTAGE]", type=click.FLOAT, required=False, default=None)
@click.pass_obj
def cli_set(obj, voltage : float | int , current : float | int):
    """
    Set VOLTAGE (V) and CURRENT (A) for channel output. "
    """
    v_set, i_set = obj.set_output(obj.channel, voltage, current)
    return f"CH{obj.channel}: {i_set} A, {v_set} V"

@wicc.command("enable")
@click.argument("state", required = True, default = 0)
@click.pass_obj
def cli_enable(obj, state : int | bool | str):
    state = 1 if state in ['on', 'ON', True, 1] else 0
    return obj.enable_output(obj.channel, state)

@wicc.command("get-current")
@click.pass_obj
def cli_get_current(obj):
    return obj.get_current(obj.channel)

@wicc.command("get-voltage")
@click.pass_obj
def cli_get_current(obj):
    return obj.get_voltage(obj.channel)

@wicc.command("meas-current")
@click.pass_obj
def cli_meas_current(obj):
    return obj.meas_voltage(obj.channel)

@wicc.command("meas-voltage")
@click.pass_obj
def cli_meas_voltage(obj):
    return obj.meas_term_voltage(obj.channel)

if __name__=='__main__':
    wicc()