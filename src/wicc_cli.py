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

@wicc.command("voltage")
@click.argument("voltage", metavar="[VOLTAGE]", type=click.FLOAT, required=False, default=None)
@click.pass_obj
def cli_voltage(obj, voltage : float | int):
    """
    Set VOLTAGE (V) for channel output, or query voltage setpoint if VOLTAGE not specified. 
    """
    if voltage is None:
        volt = obj.get_voltage(obj.channel)
        click.echo(f"{volt:.3f} V")
        return volt
    return obj.set_voltage(obj.channel, float(voltage))

@wicc.command("current")
@click.argument("current", metavar="[CURRENT]", required=False, default=None)
@click.pass_obj
def cli_current(obj, current : float | int):
    """
    "Set CURRENT (A) for channel output, or query current setpoint if CURRENT not specified. "
    """
    if current is None:
        curr = obj.get_current(obj.channel)
        click.echo(f"{curr:.2f} A")
        return curr
    return obj.set_current(obj.channel, float(current))

if __name__=='__main__':
    wicc()