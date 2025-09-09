# WIener Crate Control (WICC)

Simple command line interface for communicating with the W-Ie-Ne-R crate as a LV and HV power supply. The CLI commands can be (in principle) substituted in to the config files. 

Prerequisities:
- Python 3.7+
- *nix OS
- SNMP (see SNMP/Installation section below)

Commands:

All commands have the following syntax \
```python wicc_cli.py -d [HV|LV] channel [CHANNEL 1-8] [COMMAND]```

with the following commands available:\
-```enable [0|1]```: disables/enables the output of the selected channel
- ```get-current```: prints and returns the current setpoint in mA   
- ```get-voltage```: prints and returns the voltage setpoint in V
- ```meas-current```: prints and returns the current measured at the terminal in mA.
- ```meas-voltage```: prints and returns the voltage measured across the terminal in V
- ```set [VOLTAGE] [CURRENT]``` sets the voltage and current in V and A

```wicc_cli.py --help```, as usual, will display help for the flags and commands. You can specify the IP of the crate with the ```-i``` flag, as well as turn on logging with the verbosity flag ```-v``` or ```-vv``` and specify paths to the MIB file with ```-M``` for the directory and ```-m``` for the name. 

## Hardware

CC24: Controller for the other modules installed in the crate. CAN1 and CAN2 are for chaining other crates together in a master-slave setup.

Wiener Mpod: LV supply. 2x 37-pin D-sub connectors. Bottom 5 pins are reserved for interlock functionality.  

EHS 84 10n (SN: ): HV supply. 


## Communication

The easiest way to communicate with the crate is through the web portal. 

### Web portal 

1. Connect an Ethernet cable from the ETH port on the CC24 controller to the hub/switch connected to the DAQ PC.

2. Wait a few minutes for the connection to be established.

3. On the front display of the crate, navigate to the home screen -> Config.

4. Make a note of the assigned IP address.

5. Enter this IP address into any web browser, e.g 10.179.59.29

6. Login with the credentials: \
Username: admin \
Password: password


### SNMP

#### Installation

To install SNMP: ```sudo yum install -y net-snmp net-snmp-utils```

Add lines in the following format to the config file ( /etc/snmp/snmpd.conf):
```
createUser <username> <authenticationprotocol> <authpassphrase> <privacyprotocol> <privpassphrase>
rwuser <username> <[noauth|auth|priv <OID | -V VIEW [CONTEXT]]]>
```
e.g.

```
createUser opmd SHA password AES
rwuser testuser noauth .1
```
Then restart PC
```
systemctl stop snmpd
systemctl start snmpd
```
Copy WIENER-CRATE-MIB.txt file (either from [here](https://iseg-hv.com/download/SOFTWARE/isegSNMPcontrol/current/WIENER-CRATE-MIB.txt) or from the web portal) into ``/usr/share/snmp/mibs```.

#### Commands

Generally, SNMP command-line commands follow the syntax:

```snmpcmd  -v 2c -M path/to/mibs -m +NAME_OF_MIB -c auth $IP command.channel [type Value]```

```snmpcmd```: ```snmpwalk``` (returns groups of parameters), ```snmpget``` (reads), ```snmpset```\
```-v 2c``` :  the version of SNMP to use \
```-M path/to/mibs```: path to the MIBs, by default it is ```/usr/share/snmp/mibs``` \
```NAME_OF_MIB``` : in our case is WIENER-CRATE-MIB (NB you do not need the file extension) \
```-c auth``` : the community group with the appropriate permissions to do the command. See below for list. \
```$IP``` : the ASSIGNED IP address displayed on the crate \
command.channel : command such as outputVoltage, moduleDescription etc. See below for channel assignment. \
```[type value]``` : only relevant for set commands. Possible types are ```F``` = Float, ```i``` = integer. Boolean switches are integers, and most other values are floats. \


Community groups:

- ```public```: read 
- ```private```: Crate ON/OFF permissions
- ```admin```: change parameters such as fan speed or temperature limits
- ```guru```: change HV and LV parameters

Channel assignment:

- Slot 1 (LV) channels are numbered 0-99 (with identifiers u0-u99)
- Slot 2 (HV) channels are numbered 100-199 (with identifiers u100-u199)

These can be addressed either by number (```cmd.105```) or by identifier (```cmd.u105```)

Examples:\
```snmpset -v 2c -m +WIENER-CRATE-MIB -c guru 10.179.59.29 outputVoltage.101 F 50.0```\
:: This sets the voltage of HV CH2 of the to 50.0V, but doesn't turn it on.\
:: Note that this uses the 'guru' community group as it requires write permissions.\

```snmpset -v 2c -m +WIENER-CRATE-MIB -c guru 10.179.59.29 outputSwitch.101 i 1```\
:: This turns on the output of HV CH2.\
:: Note that the ON/OFF is an integer i 1 or i 0.\

```snmpget -v 2c -m +WIENER-CRATE-MIB -c public 10.179.59.29 outputCurrent.7```\
:: This reads the nominal set current of LV CH8.

```snmpget -v 2c -m +WIENER-CRATE-MIB -c public 10.179.59.29 outputMeasurementCurrent.5```\
:: This reads the measured current of LV CH6. \
:: The -Oqv flag makes the output less verbose. As usual, run snmpget --help for more options

```snmpwalk -v 2c -m +WIENER-CRATE-MIB -c public 10.179.59.29 outputMeasurementTerminalVoltage```\
:: Returns list of channel output voltages (measured at terminal, not setpoints)


Useful SNMP commands:

Walks:

```crate``` :: Reads back all crate parameters \
```outputName``` :: Returns list of channel names

NB: all* get commands can be run in batch, i.e. used with snmpwalk\
*I think...

The channel number should be appended to all of the below commands as described above

Square brackets indicate whether the command is read only (can only be used with snmpget) or read+write (can also be used with snmpset).

```outputVoltage``` [R/W] (F voltage)\
```outputMeasurementSenseVoltage``` [R] \
```outputMeasurementTerminalVoltage``` [R]  \
```outputVoltageRiseRate``` [R/W] (F rate) \
```outputVoltageFallRate``` [R/W] (F rate) \
```outputCurrent``` [R/W] (F current) \
```outputMeasurementCurrent``` [R] \
```outputCurrentRiseRate``` [R/W] (F rate) \
```outputCurrentFallRate``` [R/W] (F rate) \
```outputSwitch``` [R/W] (i 0|1) \
```sysMainSwitch``` [R/W] (i 0|1) \
```groupsSwitch``` [R/W] {channels: 64 = HV, 128 = LV} (i 0|1) \

For a full list of SNMP commands, consult the manual 

## HV voltage limiter

Turn off voltage limiter (should only need to do if you factory reset the crate):
1. Log in to the web portal (10.179.59.29)
2. Go into 
3. On the left-hand side, select the HV channels 
4. In the panel on the right, select "Send commands"
5. Enter the following data (leave the unit box blank):

```
Line 0
Address 1
Channel *
item Event.externalInhibitActive
Value 4
unit 
```
6. Click set item

