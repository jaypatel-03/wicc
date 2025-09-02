Topic: ASN BER decoding. 
Examples:
80 05 80 = outputOn(0) outputEnableKill(13) outputAdjusting(15) outputConstantVoltage(16)

80 0D 80 = outputOn(0) outputRampDown(12) outputEnableKill(13) outputAdjusting(15) outputConstantVoltage(16)
00 05 40 outputEnableKill(13) outputAdjusting(15) outputLowCurrentRange(17) 

MIB information:
outputStatus OBJECT-TYPE
    SYNTAX  BITS {
        outputOn (0),
        outputInhibit (1) ,
        outputFailureMinSenseVoltage (2),
        outputFailureMaxSenseVoltage (3),
        outputFailureMaxTerminalVoltage (4),
        outputFailureMaxCurrent (5),
        outputFailureMaxTemperature (6),
        outputFailureMaxPower (7),
        -- reserved
        outputFailureTimeout (9),
        outputCurrentLimited (10),
        outputRampUp (11),
        outputRampDown (12),
        outputEnableKill(13),
        outputEmergencyOff (14),
        outputAdjusting (15),
        outputConstantVoltage (16),
        outputLowCurrentRange (17),
        outputCurrentBoundsExceeded (18),
        outputFailureCurrentLimit (19),
        outputCurrentIncreasing (20),
        outputCurrentDecreasing (21),
        outputConstantPower (22),
        outputVoltageRampSpeedLimited (23),
        outputVoltageBottomReached (24),
        outputInitCrcCheckBad (25)
    }
    MAX-ACCESS  read-only
    STATUS  current
    DESCRIPTION
            "A bit string which shows the status (health and operating conditions) of one output channel.
             If a bit is set (1), the explanation is satisfied:
                outputOn (0),                           output channel is on
                outputInhibit(1),                       external (hardware-)inhibit of the output channel
                outputFailureMinSenseVoltage (2)        Supervision limit hurt: Sense voltage is too low
                outputFailureMaxSenseVoltage (3)        Supervision limit hurt: Sense voltage is too high
                outputFailureMaxTerminalVoltage (4)     Supervision limit hurt: Terminal voltage is too high
                outputFailureMaxCurrent (5)             Supervision limit hurt: Current is too high
                outputFailureMaxTemperature (6)         Supervision limit hurt: Heat sink temperature is too high
                outputFailureMaxPower (7)               Supervision limit hurt: Output power is too high
                outputFailureTimeout (9)                Communication timeout between output channel and main control
                outputCurrentLimited (10)               Current limiting is active (constant current mode)
                outputRampUp (11)                       Output voltage is increasing (e.g. after switch on)
                outputRampDown (12)                     Output voltage is decreasing (e.g. after switch off)
                outputEnableKill (13)                   EnableKill is active
                outputEmergencyOff (14)                 EmergencyOff event is active
                outputAdjusting (15)                    Fine adjustment is working
                outputConstantVoltage (16)              Voltage control (constant voltage mode)
                outputLowCurrentRange (17)              The channel is operating in the low current measurement range
                outputCurrentBoundsExceeded (18)        Output current is out of bounds
                outputFailureCurrentLimit (19)          Hardware current limit (EHS) / trip (EDS, EBS) was exceeded
                outputCurrentIncreasing (20)            Output current is increasing
                outputCurrentDecreasing (21)            Output current is decreasing
                outputConstantPower (22)                Power control (constant power mode)
                outputVoltageRampSpeedLimited (23)      HV special: VoltageRampSpeed was limited because EnableKill or DelayedTrip is configured
                outputVoltageBottomReached (24)         HV special: After a current trip the voltage bottom is reached
                outputInitCrcCheckBad (25)              Initial selftest failed

Given the above information, how can I determine the output status from the bits given?