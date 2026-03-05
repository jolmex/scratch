# RFFC5071 RF Synthesizer Control

Python console application to control the RFFC5071 wideband synthesizer/VCO via its proprietary 3-wire serial interface on Raspberry Pi.

## Features

- ✓ Native 3-wire serial interface (ENX, SCLK, SDATA)
- ✓ GPIO bit-banging mode or SPI-compatible mode
- ✓ Device detection and communication check
- ✓ Read all 32 registers with detailed information
- ✓ Write to any register
- ✓ Set VCO frequency (272-5400 MHz)
- ✓ Enable/disable outputs for Path 1 and Path 2
- ✓ VCO calibration
- ✓ Status summary with frequency calculations
- ✓ Interactive console interface
- ✓ Command-line argument support

## About the 3-Wire Interface

The RFFC5071 uses a **proprietary 3-wire serial bus** (not standard SPI or I2C):

- **ENX** - Serial enable/latch (acts like chip select)
- **SCLK** - Clock signal  
- **SDATA** - Bidirectional data (3-wire) or data-in (4-wire)

**Write transaction:** 24 bits MSB-first
- bit 23: X (don't care)
- bit 22: R/W (0=write, 1=read)
- bit 21-15: 7-bit register address
- bit 14-0: 16-bit data value

The timing is compatible with SPI mode 0 (sample on rising edge), but ENX must be controlled separately.

## Hardware Setup

### Raspberry Pi 3-Wire Connection

Connect the RFFC5071 to your Raspberry Pi GPIO pins:

| RFFC5071 Pin | Raspberry Pi Pin | Default GPIO | Description |
|--------------|------------------|--------------|-------------|
| ENX          | GPIO 27          | BCM 27       | Enable/Latch |
| SCLK         | GPIO 17          | BCM 17       | Clock       |
| SDATA        | GPIO 4           | BCM 4        | Data        |
| GND          | GND              | -            | Ground      |
| VCC          | 3.3V             | -            | Power       |

**Optional control pins:**
- **RESETX** - Active-low reset (connect to GPIO, keep HIGH for normal operation)
- **ENBL** - Enable signal (connect to GPIO, typically HIGH)
- **MODE** - Operating mode selection (often hardwired)

### GPIO vs SPI Mode

**GPIO Mode (Recommended for testing):**
- Direct bit-banging on GPIO pins
- Full control, easy to debug
- Works on any 3 GPIO pins
- No SPI peripheral configuration needed

**SPI Mode:**
- Uses hardware SPI peripheral for SCLK/SDATA
- ENX controlled separately via GPIO
- Faster, less CPU intensive
- Requires SPI enabled: `sudo raspi-config` → Interface Options → SPI

### Pin Mapping Reference

Default pins are chosen to avoid conflicts with other common peripherals:
- **GPIO 27** = ENX (available, not used by SPI/I2C/UART)
- **GPIO 17** = SCLK (available, sometimes used for SPI1)
- **GPIO 4** = SDATA (available, GPCLK0 alternate function)

You can use different pins with the `--enx`, `--sclk`, `--sdata` arguments.

## Installation

1. **Install Python dependencies:**

```bash
# For GPIO bit-banging mode (recommended)
pip3 install RPi.GPIO

# For SPI mode (optional, faster)
pip3 install spidev

# Install both for maximum flexibility
pip3 install RPi.GPIO spidev
```

2. **GPIO Permissions:**

```bash
# Add user to gpio group (logout/login required)
sudo usermod -a -G gpio $USER

# Or run as root (not recommended)
sudo python3 rffc.py
```

3. **Make the script executable (optional):**

```bash
chmod +x rffc.py
```

## Usage

### Run the Console

**Interactive mode (GPIO bit-banging, default):**

```bash
python3 rffc.py
# or
sudo python3 rffc.py  # if not in gpio group
```

**Interactive mode (SPI peripheral):**

```bash
python3 rffc.py -m spi
```

**Command-line mode (execute command and exit):**

```bash
# Check device (GPIO mode)
python3 rffc.py check

# Set frequency (SPI mode)
python3 rffc.py -m spi freq 1000

# Read all registers
python3 rffc.py read

# Write register
python3 rffc.py write 0x0C 0x1234

# Enable output
python3 rffc.py enable 1

# Get status
python3 rffc.py status
```

**Custom GPIO pins:**

```bash
# Use different pins: ENX=GPIO7, SCLK=GPIO17, SDATA=GPIO27
python3 rffc.py --enx 7 --sclk 17 --sdata 27 check

# With hardware control pins
python3 rffc.py --resetx 25 --enbl 24 check
```

**Custom reference frequency:**

```bash
# 26 MHz reference oscillator
python3 rffc.py -r 26.0 freq 1000
```

**Scripting examples:**

```bash
# Initialize and configure
python3 rffc.py reset
python3 rffc.py freq 2400 1
python3 rffc.py enable 1
python3 rffc.py status

# Chain commands
python3 rffc.py check && python3 rffc.py freq 1000 && python3 rffc.py enable 1
```

### Available Commands

#### Device Commands

- `check` - Check if RFFC5071 is responding and read device ID
- `read` - Read and display all 32 registers with their meanings
- `reset` - Reset all registers to default power-on values
- `status` - Display comprehensive status summary

#### Frequency Control

- `freq <MHz> [path]` - Set frequency (272-5400 MHz, default path=1)
  - Examples:
    - `freq 1000` - Set Path 1 to 1000 MHz
    - `freq 2400 2` - Set Path 2 to 2400 MHz
    - `freq 5000 1` - Set Path 1 to 5 GHz

- `enable <path>` - Enable output for Path 1 or 2
  - `enable 1` - Enable Path 1 output
  - `enable 2` - Enable Path 2 output

- `disable <path>` - Disable output for Path 1 or 2
  - `disable 1` - Disable Path 1 output

- `cal` - Trigger VCO calibration manually

#### Register Access

- `read <addr>` - Read single register (hexadecimal address)
  - Example: `read 0x0C` - Read P1_FREQ1 register

- `write <addr> <value>` - Write to register (hex values)
  - Example: `write 0x0C 0x1234` - Write 0x1234 to register 0x0C

#### Other

- `help` - Show command menu
- `quit` or `exit` - Exit the program (interactive mode only)

### Command-Line Arguments

```
usage: rffc.py [-h] [-m {gpio,spi}] [--enx ENX] [--sclk SCLK] [--sdata SDATA]
               [-b BUS] [-d DEVICE] [--resetx RESETX] [--enbl ENBL]
               [-r REF_FREQ] [command ...]

RFFC5071 RF Synthesizer Control (3-wire serial interface)

positional arguments:
  command               Command to execute (e.g., check, freq 1000, read, status)

optional arguments:
  -h, --help            show this help message and exit
  -m {gpio,spi}, --mode {gpio,spi}
                        Interface mode: gpio (bit-bang) or spi (default: gpio)
  --enx ENX             GPIO pin for ENX (enable/latch, default: 27)
  --sclk SCLK           GPIO pin for SCLK (clock, default: 17)
  --sdata SDATA         GPIO pin for SDATA (data, default: 4)
  -b BUS, --bus BUS     SPI bus number (for spi mode, default: 0)
  -d DEVICE, --device DEVICE
                        SPI device number (for spi mode, default: 0)
  --resetx RESETX       GPIO pin for RESETX (optional)
  --enbl ENBL           GPIO pin for ENBL (optional)
  -r REF_FREQ, --ref-freq REF_FREQ
                        Reference frequency in MHz (default: 50.0)
```

## Example Session

```
$ python3 rffc.py

RFFC5071 RF Synthesizer Control
================================

✓ GPIO initialized: ENX=27, SCLK=17, SDATA=4

rffc> check
==================================================
Device Readback Register: 0x0410
Device ID: 0x01 (Expected: 0x01 for RFFC5071)
✓ RFFC5071 device detected and responding!

rffc> freq 1000
============================================================
Setting Path 1 Frequency: 1000.0 MHz
VCO Frequency: 2000.0 MHz
LO Divider: 1 (÷2)
N: 40, NUM: 0 (0x0000)
Calculated: 50.0 * (40 + 0/65536) = 2000.000000 MHz
============================================================
Triggering VCO calibration...
✓ VCO calibration complete
✓ Frequency set to 1000.0 MHz on Path 1

rffc> enable 1
✓ Path 1 output enabled

rffc> status
============================================================
RFFC5071 STATUS SUMMARY
============================================================
Reference Frequency: 50.0 MHz

Path 1:
  N=40, NUM=0, LODIV=1 (÷2)
  VCO Frequency: 2000.000 MHz
  Output Frequency: 1000.000 MHz
  Output Enabled: True

Path 2:
  N=8, NUM=0, LODIV=0 (÷1)
  VCO Frequency: 400.000 MHz
  Output Frequency: 400.000 MHz
  Output Enabled: False
============================================================

rffc> read
================================================================================
RFFC5071 REGISTER DUMP
================================================================================
Addr   Name                                Hex      Binary            Dec   
--------------------------------------------------------------------------------
0x00   LF (Loop Filter Configuration)      0xBEFA   1011111011111010  48890
0x01   XO (Crystal Oscillator Config)      0x4064   0100000001100100  16484
0x02   CAL_TIME (Calibration Time)         0x5000   0101000000000000  20480
...
================================================================================

rffc> quit
SPI connection closed
Goodbye!
```

## Frequency Range and LO Divider

The RFFC5071 automatically selects the appropriate LO divider based on the requested frequency:

| Output Frequency | VCO Frequency | LO Divider |
|------------------|---------------|------------|
| 2700-5400 MHz    | 2700-5400 MHz | ÷1         |
| 1350-2700 MHz    | 2700-5400 MHz | ÷2         |
| 675-1350 MHz     | 2700-5400 MHz | ÷4         |
| 272-675 MHz      | 2176-5400 MHz | ÷8         |

## Register Map

The RFFC5071 has 32 registers (0x00-0x1F):

- **0x00:** LF - Loop Filter Configuration
- **0x01:** XO - Crystal Oscillator Configuration
- **0x02:** CAL_TIME - Calibration Time
- **0x03:** VCO_CTRL - VCO Control
- **0x04-0x08:** Calibration registers
- **0x09-0x0B:** PLL and Mixer Control
- **0x0C-0x0E:** Path 1 Frequency Control (FREQ1, FREQ2, FREQ3)
- **0x0F-0x11:** Path 2 Frequency Control (FREQ1, FREQ2, FREQ3)
- **0x12-0x1E:** Additional control registers
- **0x1F:** READBACK - Device ID and Status (read-only)

## Frequency Calculation

The output frequency is calculated using the fractional-N PLL:

```
f_out = f_ref × (N + NUM/65536) / (2^lodiv)
```

Where:
- `f_ref` = Reference frequency (default 50 MHz)
- `N` = Integer divider (8-bit value, 16-255)
- `NUM` = Fractional divider (16-bit value, 0-65535)
- `lodiv` = LO divider select (0-3 for ÷1, ÷2, ÷4, ÷8)

## Troubleshooting

### GPIO Not Available

If you get "RPi.GPIO not available":
```bash
pip3 install RPi.GPIO
```

### Permission Denied

If you get permission errors:
```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER
# Log out and log back in

# Or run with sudo (quick test)
sudo python3 rffc.py
```

### Device Not Responding

If device ID check fails:
1. Check all wiring connections (ENX, SCLK, SDATA, GND, VCC)
2. Verify 3.3V power supply (RFFC5071 is 3.3V logic)
3. Check ground connection
4. Verify GPIO pin numbers match your wiring
5. Try slower bit timing (edit delays in `_write_24bits_gpio`)
6. Check RESETX is HIGH if connected (active low)
7. Check ENBL is HIGH if connected

### Reading Issues

If reads don't work:
- GPIO mode: Should work with bidirectional SDATA
- SPI mode: May need 4-wire configuration
- Alternatively: rely on write cache (register values are cached after write)

### SPI Mode Not Working

If SPI mode fails:
```bash
# Enable SPI peripheral
sudo raspi-config  # → Interface Options → SPI → Enable
sudo reboot

# Check SPI devices exist
ls /dev/spidev*

# Try GPIO mode instead
python3 rffc.py -m gpio check
```

## Customization

### Change Reference Frequency

If you're using a different reference oscillator:

```python
rffc = RFFC5071(ref_freq=26.0)  # 26 MHz reference
```

### Change GPIO Pins

If using different GPIO pins:

```python
rffc = RFFC5071(enx_pin=7, sclk_pin=17, sdata_pin=27)
```

### Add Hardware Control Pins

For full hardware control:

```python
rffc = RFFC5071(
    enx_pin=8, sclk_pin=11, sdata_pin=10,
    resetx_pin=25,  # Active low reset
    enbl_pin=24     # Enable signal
)
```

## Implementation Notes

### 24-Bit Protocol Format

```
MSB                                                    LSB
[X][R/W][A6][A5][A4][A3][A2][A1][A0][D15]...[D1][D0]
 │   │   └────────┬────────┘        └─────┬─────┘
 │   │         Address(7)              Data(16)
 │   └─ 0=Write, 1=Read
 └─ Don't care
```

### Timing

GPIO bit-bang mode uses 1µs delays between state changes (conservative for debugging). For faster operation, reduce delays in `_write_24bits_gpio()`.

### HackRF Reference

The HackRF project uses RFFC5071 and provides reference implementations:
- See `hackrf_rffc5071_write()` and `hackrf_rffc5071_read()` in HackRF firmware
- Validates the 3-wire protocol timing and bit ordering

## License

This code is provided as-is for educational and development purposes.

## References

- RFFC5071 Datasheet: [QORVO/RFMD RFFC5071](https://www.qorvo.com/)
- HackRF Project: [github.com/greatscottgadgets/hackrf](https://github.com/greatscottgadgets/hackrf) (uses RFFC5071)
- RPi.GPIO Documentation: [pypi.org/project/RPi.GPIO/](https://pypi.org/project/RPi.GPIO/)
- Raspberry Pi GPIO Pinout: [pinout.xyz](https://pinout.xyz/)
