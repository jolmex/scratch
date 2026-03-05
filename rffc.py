#!/usr/bin/env python3
"""
RFFC5071 RF Synthesizer Control via 3-Wire Serial Interface
GPIO bit-banging implementation for Raspberry Pi

The RFFC5071 uses a proprietary 3-wire serial interface:
- ENX (serial enable/latch, acts like chip select)
- SCLK (clock)
- SDATA (bidirectional data)

Write format: 24 bits MSB-first
  bit23: X (don't care)
  bit22: R/W (0=write, 1=read)
  bit21-15: 7-bit register address
  bit14-0: 16-bit data
"""

import time
import sys
import argparse

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("Error: RPi.GPIO not available. Install with: pip3 install RPi.GPIO")
    sys.exit(1)

class RFFC5071:
    """RFFC5071 Wideband Synthesizer/VCO with Integrated LO Switch"""
    
    # Register definitions (0x00 to 0x1E = 31 registers)
    REGISTERS = {
        0x00: "LF (Loop Filter Configuration)",
        0x01: "XO (Crystal Oscillator Configuration)",
        0x02: "CAL_TIME (Calibration Time)",
        0x03: "VCO_CTRL (VCO Control)",
        0x04: "CT_CAL1 (Coarse Tune Calibration 1)",
        0x05: "CT_CAL2 (Coarse Tune Calibration 2)",
        0x06: "PLL_CAL1 (PLL Calibration 1)",
        0x07: "PLL_CAL2 (PLL Calibration 2)",
        0x08: "VCO_AUTO (VCO Auto-calibration)",
        0x09: "PLL_CTRL (PLL Control)",
        0x0A: "PLL_BIAS (PLL Bias)",
        0x0B: "MIX_CONT (Mixer Control)",
        0x0C: "P1_FREQ1 (Path 1 Frequency Control 1)",
        0x0D: "P1_FREQ2 (Path 1 Frequency Control 2)",
        0x0E: "P1_FREQ3 (Path 1 Frequency Control 3)",
        0x0F: "P2_FREQ1 (Path 2 Frequency Control 1)",
        0x10: "P2_FREQ2 (Path 2 Frequency Control 2)",
        0x11: "P2_FREQ3 (Path 2 Frequency Control 3)",
        0x12: "FN_CTRL (Divider Control)",
        0x13: "EXT_MOD (External Modulation)",
        0x14: "FMOD (Frequency Modulation)",
        0x15: "SDI_CTRL (SDI Control)",
        0x16: "GPO (General Purpose Output)",
        0x17: "T_VCO (VCO Test)",
        0x18: "IQMOD1 (IQ Modulator 1)",
        0x19: "IQMOD2 (IQ Modulator 2)",
        0x1A: "IQMOD3 (IQ Modulator 3)",
        0x1B: "IQMOD4 (IQ Modulator 4)",
        0x1C: "T_CTRL (Test Control)",
        0x1D: "DEV_CTRL (Device Control)",
        0x1E: "TEST (Test)",
        0x1F: "READBACK (Device ID/Status)"
    }
    
    # Default register values (power-on reset values)
    DEFAULT_VALUES = {
        0x00: 0xBEFA,  # LF
        0x01: 0x4064,  # XO
        0x02: 0x5000,  # CAL_TIME
        0x03: 0x0965,  # VCO_CTRL
        0x04: 0x1800,  # CT_CAL1
        0x05: 0x7FE0,  # CT_CAL2
        0x06: 0x7FE0,  # PLL_CAL1
        0x07: 0x1800,  # PLL_CAL2
        0x08: 0x7FE0,  # VCO_AUTO
        0x09: 0x2000,  # PLL_CTRL
        0x0A: 0x0028,  # PLL_BIAS
        0x0B: 0x0000,  # MIX_CONT
        0x0C: 0x0800,  # P1_FREQ1
        0x0D: 0x0000,  # P1_FREQ2
        0x0E: 0x0000,  # P1_FREQ3
        0x0F: 0x0800,  # P2_FREQ1
        0x10: 0x0000,  # P2_FREQ2
        0x11: 0x0000,  # P2_FREQ3
        0x12: 0x4900,  # FN_CTRL
        0x13: 0x0000,  # EXT_MOD
        0x14: 0x0000,  # FMOD
        0x15: 0x0000,  # SDI_CTRL
        0x16: 0x0000,  # GPO
        0x17: 0x0000,  # T_VCO
        0x18: 0x0000,  # IQMOD1
        0x19: 0x0000,  # IQMOD2
        0x1A: 0x0000,  # IQMOD3
        0x1B: 0x0000,  # IQMOD4
        0x1C: 0x0000,  # T_CTRL
        0x1D: 0x0000,  # DEV_CTRL
        0x1E: 0x0000,  # TEST
    }
    
    def __init__(self, enx_pin=27, sclk_pin=17, sdata_pin=4, ref_freq=50.0,
                 resetx_pin=None, enbl_pin=None):
        """
        Initialize RFFC5071 control via GPIO bit-banging
        
        Args:
            enx_pin: GPIO pin for ENX (enable/latch) - default GPIO27
            sclk_pin: GPIO pin for SCLK (clock) - default GPIO17
            sdata_pin: GPIO pin for SDATA (data) - default GPIO4
            ref_freq: Reference frequency in MHz (default 50.0 MHz)
            resetx_pin: Optional GPIO pin for RESETX
            enbl_pin: Optional GPIO pin for ENBL
        """
        self.ref_freq = ref_freq
        self.register_cache = {}
        self.enx_pin = enx_pin
        self.sclk_pin = sclk_pin
        self.sdata_pin = sdata_pin
        self.resetx_pin = resetx_pin
        self.enbl_pin = enbl_pin
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup ENX (output, high = idle)
        GPIO.setup(enx_pin, GPIO.OUT)
        GPIO.output(enx_pin, GPIO.HIGH)
        
        # Setup SCLK (output, low = idle)
        GPIO.setup(sclk_pin, GPIO.OUT)
        GPIO.output(sclk_pin, GPIO.LOW)
        
        # Setup SDATA (start as output for write)
        GPIO.setup(sdata_pin, GPIO.OUT)
        GPIO.output(sdata_pin, GPIO.LOW)
        
        # Setup optional control pins
        if resetx_pin:
            GPIO.setup(resetx_pin, GPIO.OUT)
            GPIO.output(resetx_pin, GPIO.HIGH)  # Active low, so HIGH = not reset
        
        if enbl_pin:
            GPIO.setup(enbl_pin, GPIO.OUT)
            GPIO.output(enbl_pin, GPIO.HIGH)  # Typically HIGH = enabled
        
        print(f"✓ GPIO initialized: ENX={enx_pin}, SCLK={sclk_pin}, SDATA={sdata_pin}")
    
    def close(self):
        """Close GPIO and cleanup"""
        GPIO.cleanup()
        print("GPIO closed")
    
    def _write_24bits(self, word24):
        """
        Bit-bang 24 bits over 3-wire interface using GPIO
        
        Args:
            word24: 24-bit word to write
        """
        # ENX low to start transaction
        GPIO.output(self.enx_pin, GPIO.LOW)
        time.sleep(0.00001)  # ENX setup time (10µs)
        
        # Clock out 24 bits, MSB first
        for i in range(23, -1, -1):
            bit = (word24 >> i) & 1
            
            # Ensure clock is low before setting data
            GPIO.output(self.sclk_pin, GPIO.LOW)
            time.sleep(0.000005)  # Clock low time (5µs)
            
            # Set data bit and let it settle
            GPIO.output(self.sdata_pin, GPIO.HIGH if bit else GPIO.LOW)
            time.sleep(0.000005)  # Data setup time (5µs) - critical for stability
            
            # Clock high (device samples on rising edge)
            GPIO.output(self.sclk_pin, GPIO.HIGH)
            time.sleep(0.000005)  # Clock high time (5µs)
        
        # Final clock low
        GPIO.output(self.sclk_pin, GPIO.LOW)
        time.sleep(0.000005)
        
        # ENX high to latch
        GPIO.output(self.enx_pin, GPIO.HIGH)
        time.sleep(0.00001)  # Hold time (10µs)
    
    def write_register(self, addr, value):
        """
        Write to a register
        
        Format: 24 bits = X(1) + R/W(0) + addr(7) + data(16)
        
        Args:
            addr: Register address (0x00 to 0x1E)
            value: 16-bit value to write
        """
        if addr > 0x1E:
            raise ValueError(f"Invalid register address: 0x{addr:02X}")
        
        # Build 24-bit word:
        # bit23: X (don't care) = 0
        # bit22: R/W = 0 (write)
        # bit21-15: 7-bit address
        # bit14-0: 16-bit data
        word24 = (0 << 23) | (0 << 22) | ((addr & 0x7F) << 15) | (value & 0xFFFF)
        
        self._write_24bits(word24)
        self.register_cache[addr] = value
        time.sleep(0.001)  # Small delay between operations
    
    def _read_24bits(self, word24_send):
        """
        Bit-bang read over 3-wire interface (bidirectional SDATA)
        
        Args:
            word24_send: 24-bit word to send (with R/W=1 for read)
            
        Returns:
            16-bit data read from device
        """
        # ENX low to start transaction
        GPIO.output(self.enx_pin, GPIO.LOW)
        time.sleep(0.00001)  # ENX setup time (10µs)
        
        # Clock out 9 bits (X + R/W + 7 addr bits), MSB first
        for i in range(23, 14, -1):  # Fixed: 23→15 inclusive (9 bits)
            bit = (word24_send >> i) & 1
            
            GPIO.output(self.sclk_pin, GPIO.LOW)
            time.sleep(0.000005)  # Clock low time
            
            GPIO.output(self.sdata_pin, GPIO.HIGH if bit else GPIO.LOW)
            time.sleep(0.000005)  # Data setup time
            
            GPIO.output(self.sclk_pin, GPIO.HIGH)
            time.sleep(0.000005)  # Clock high time
        
        # Final clock low before switching direction
        GPIO.output(self.sclk_pin, GPIO.LOW)
        time.sleep(0.000005)
        
        # Set SDATA low before releasing (reduces conflict)
        GPIO.output(self.sdata_pin, GPIO.LOW)
        time.sleep(0.000002)
        
        # Switch SDATA to input for reading (release bus to device)
        GPIO.setup(self.sdata_pin, GPIO.IN)
        time.sleep(0.00002)  # Increased turnaround time (20µs)
        
        # Clock in 16 bits of data
        data = 0
        for i in range(15, -1, -1):
            GPIO.output(self.sclk_pin, GPIO.LOW)
            time.sleep(0.000005)  # Clock low time
            
            GPIO.output(self.sclk_pin, GPIO.HIGH)
            time.sleep(0.000003)  # Wait before sampling (3µs)
            
            bit = GPIO.input(self.sdata_pin)
            data |= (bit << i)
            
            time.sleep(0.000002)  # Clock high hold time (2µs)
        
        # Final clock low
        GPIO.output(self.sclk_pin, GPIO.LOW)
        time.sleep(0.000005)
        
        # ENX high FIRST (end transaction, device releases bus)
        GPIO.output(self.enx_pin, GPIO.HIGH)
        time.sleep(0.00002)  # Wait for device to release SDATA (20µs)
        
        # NOW switch SDATA back to output and set to idle LOW
        GPIO.setup(self.sdata_pin, GPIO.OUT)
        GPIO.output(self.sdata_pin, GPIO.LOW)
        time.sleep(0.000005)
        
        return data
    
    def read_register(self, addr):
        """
        Read from a register
        
        Format: Send 24 bits = X(1) + R/W(1) + addr(7) + dummy(16)
        Then read back 16 bits of data
        
        Args:
            addr: Register address (0x00 to 0x1F)
            
        Returns:
            16-bit register value
        """
        if addr > 0x1F:
            raise ValueError(f"Invalid register address: 0x{addr:02X}")
        
        # Build 24-bit word for read:
        # bit23: X (don't care) = 0
        # bit22: R/W = 1 (read)
        # bit21-15: 7-bit address
        # bit14-0: dummy data (will be replaced by device response)
        word24 = (0 << 23) | (1 << 22) | ((addr & 0x7F) << 15) | 0x0000
        
        value = self._read_24bits(word24)
        self.register_cache[addr] = value
        return value
    
    def read_all_registers(self):
        """Read all registers (0x00 to 0x1F)"""
        print("\n" + "="*80)
        print("RFFC5071 REGISTER DUMP")
        print("="*80)
        print(f"{'Addr':<6} {'Name':<35} {'Hex':<8} {'Binary':<18} {'Dec':<6}")
        print("-"*80)
        
        for addr in range(0x20):
            try:
                value = self.read_register(addr)
                name = self.REGISTERS.get(addr, "Reserved/Unknown")
                print(f"0x{addr:02X}   {name:<35} 0x{value:04X}  {value:016b}  {value:5d}")
            except Exception as e:
                print(f"0x{addr:02X}   Error reading: {e}")
        
        print("="*80)
    
    def check_device_id(self):
        """Check if device is responding by reading device ID"""
        try:
            # Read register 0x1F (READBACK) which contains device ID
            readback = self.read_register(0x1F)
            device_id = (readback >> 10) & 0x3F  # Bits 15:10
            
            print(f"\n{'='*50}")
            print(f"Device Readback Register: 0x{readback:04X}")
            print(f"Device ID: 0x{device_id:02X} (Expected: 0x01 for RFFC5071)")
            
            if device_id == 0x01:
                print("✓ RFFC5071 device detected and responding!")
                return True
            else:
                print(f"✗ Unexpected device ID: 0x{device_id:02X}")
                return False
        except Exception as e:
            print(f"✗ Failed to communicate with device: {e}")
            return False
    
    def reset_to_defaults(self):
        """Write default values to all registers"""
        print("\nResetting all registers to default values...")
        for addr, value in self.DEFAULT_VALUES.items():
            self.write_register(addr, value)
            print(f"  0x{addr:02X} = 0x{value:04X}")
        print("✓ Reset complete")
    
    def set_frequency(self, freq_mhz, path=1):
        """
        Set VCO frequency for a given path
        
        Args:
            freq_mhz: Desired frequency in MHz (272 to 5400 MHz)
            path: Path number (1 or 2)
        
        The RFFC5071 uses a fractional-N PLL with the formula:
        f_vco = f_ref * (N + NUM/2^16) / (2^lodiv)
        
        Where:
        - f_ref is the reference frequency (typically 50 MHz)
        - N is the integer divider (stored in bits 15:8 of FREQ1)
        - NUM is the fractional divider (16-bit value in FREQ2 and low bits of FREQ3)
        - lodiv is the LO divider (0, 1, 2, or 3 for divide by 1, 2, 4, or 8)
        """
        if freq_mhz < 272 or freq_mhz > 5400:
            print(f"✗ Frequency {freq_mhz} MHz out of range (272-5400 MHz)")
            return False
        
        # Determine appropriate LO divider
        if freq_mhz >= 2700:
            lodiv = 0  # Divide by 1
            vco_freq = freq_mhz
        elif freq_mhz >= 1350:
            lodiv = 1  # Divide by 2
            vco_freq = freq_mhz * 2
        elif freq_mhz >= 675:
            lodiv = 2  # Divide by 4
            vco_freq = freq_mhz * 4
        else:
            lodiv = 3  # Divide by 8
            vco_freq = freq_mhz * 8
        
        # Calculate N and NUM for fractional-N PLL
        # f_vco = f_ref * (N + NUM/65536)
        pll_ratio = vco_freq / self.ref_freq
        N = int(pll_ratio)
        frac = pll_ratio - N
        NUM = int(frac * 65536)
        
        # Ensure N is in valid range (typically 16 to 255)
        if N < 16 or N > 255:
            print(f"✗ Calculated N={N} out of range")
            return False
        
        print(f"\n{'='*60}")
        print(f"Setting Path {path} Frequency: {freq_mhz} MHz")
        print(f"VCO Frequency: {vco_freq} MHz")
        print(f"LO Divider: {lodiv} (÷{2**lodiv})")
        print(f"N: {N}, NUM: {NUM} (0x{NUM:04X})")
        print(f"Calculated: {self.ref_freq} * ({N} + {NUM}/65536) = {vco_freq:.6f} MHz")
        print(f"{'='*60}")
        
        # Select register base based on path
        if path == 1:
            freq1_addr, freq2_addr, freq3_addr = 0x0C, 0x0D, 0x0E
        elif path == 2:
            freq1_addr, freq2_addr, freq3_addr = 0x0F, 0x10, 0x11
        else:
            print(f"✗ Invalid path: {path} (must be 1 or 2)")
            return False
        
        # Read current FREQ1 to preserve other settings
        freq1 = self.read_register(freq1_addr)
        
        # Update FREQ1: bits [15:8] = N, bits [7:6] = lodiv
        freq1 = (freq1 & 0x003F) | (N << 8) | (lodiv << 6)
        
        # FREQ2: bits [15:0] = NUM[15:0]
        freq2 = NUM & 0xFFFF
        
        # FREQ3: typically used for extended fractional bits (often 0)
        freq3 = 0x0000
        
        # Write frequency registers
        self.write_register(freq1_addr, freq1)
        self.write_register(freq2_addr, freq2)
        self.write_register(freq3_addr, freq3)
        
        # Trigger VCO calibration
        self.calibrate_vco()
        
        print(f"✓ Frequency set to {freq_mhz} MHz on Path {path}")
        return True
    
    def calibrate_vco(self):
        """Trigger VCO calibration"""
        print("Triggering VCO calibration...")
        
        # Read current VCO_CTRL register
        vco_ctrl = self.read_register(0x03)
        
        # Set CAL bit (typically bit 14) to trigger calibration
        vco_ctrl |= (1 << 14)
        self.write_register(0x03, vco_ctrl)
        
        # Wait for calibration to complete
        time.sleep(0.01)
        
        # Clear CAL bit
        vco_ctrl &= ~(1 << 14)
        self.write_register(0x03, vco_ctrl)
        
        print("✓ VCO calibration complete")
    
    def enable_output(self, path=1, enable=True):
        """Enable or disable mixer output for a path"""
        mix_cont = self.read_register(0x0B)
        
        if path == 1:
            if enable:
                mix_cont |= (1 << 0)  # Enable Path 1
            else:
                mix_cont &= ~(1 << 0)
        elif path == 2:
            if enable:
                mix_cont |= (1 << 1)  # Enable Path 2
            else:
                mix_cont &= ~(1 << 1)
        
        self.write_register(0x0B, mix_cont)
        status = "enabled" if enable else "disabled"
        print(f"✓ Path {path} output {status}")
    
    def get_status_summary(self):
        """Display key status information"""
        print("\n" + "="*60)
        print("RFFC5071 STATUS SUMMARY")
        print("="*60)
        
        # Read key registers
        vco_ctrl = self.read_register(0x03)
        pll_ctrl = self.read_register(0x09)
        mix_cont = self.read_register(0x0B)
        p1_freq1 = self.read_register(0x0C)
        p1_freq2 = self.read_register(0x0D)
        p2_freq1 = self.read_register(0x0F)
        p2_freq2 = self.read_register(0x10)
        
        # Decode Path 1
        p1_n = (p1_freq1 >> 8) & 0xFF
        p1_lodiv = (p1_freq1 >> 6) & 0x03
        p1_num = p1_freq2
        p1_vco = self.ref_freq * (p1_n + p1_num/65536.0)
        p1_freq = p1_vco / (2 ** p1_lodiv)
        
        # Decode Path 2
        p2_n = (p2_freq1 >> 8) & 0xFF
        p2_lodiv = (p2_freq1 >> 6) & 0x03
        p2_num = p2_freq2
        p2_vco = self.ref_freq * (p2_n + p2_num/65536.0)
        p2_freq = p2_vco / (2 ** p2_lodiv)
        
        print(f"Reference Frequency: {self.ref_freq} MHz")
        print(f"\nPath 1:")
        print(f"  N={p1_n}, NUM={p1_num}, LODIV={p1_lodiv} (÷{2**p1_lodiv})")
        print(f"  VCO Frequency: {p1_vco:.3f} MHz")
        print(f"  Output Frequency: {p1_freq:.3f} MHz")
        print(f"  Output Enabled: {bool(mix_cont & 0x01)}")
        
        print(f"\nPath 2:")
        print(f"  N={p2_n}, NUM={p2_num}, LODIV={p2_lodiv} (÷{2**p2_lodiv})")
        print(f"  VCO Frequency: {p2_vco:.3f} MHz")
        print(f"  Output Frequency: {p2_freq:.3f} MHz")
        print(f"  Output Enabled: {bool(mix_cont & 0x02)}")
        
        print("="*60)


def print_menu():
    """Print command menu"""
    print("\n" + "="*60)
    print("RFFC5071 CONTROL CONSOLE (3-Wire Serial Interface)")
    print("="*60)
    print("Device Commands:")
    print("  check       - Check if device is responding")
    print("  read        - Read and display all registers")
    print("  reset       - Reset all registers to default values")
    print("  status      - Display status summary")
    print("\nFrequency Control:")
    print("  freq <MHz> [path]  - Set frequency (path 1 or 2, default=1)")
    print("                      Example: freq 1000 1")
    print("  enable <path>      - Enable output (path 1 or 2)")
    print("  disable <path>     - Disable output (path 1 or 2)")
    print("  cal                - Trigger VCO calibration")
    print("\nRegister Access:")
    print("  read <addr>        - Read single register (hex)")
    print("                      Example: read 0x0C")
    print("  write <addr> <val> - Write register (hex values)")
    print("                      Example: write 0x0C 0x1234")
    print("\nOther:")
    print("  help        - Show this menu")
    print("  quit/exit   - Exit program")
    print("="*60)


def execute_command(rffc, cmd_input):
    """Execute a single command and return True if should continue, False if should exit"""
    if not cmd_input:
        return True
    
    parts = cmd_input.strip().split()
    cmd = parts[0].lower()
    
    if cmd in ['quit', 'exit', 'q']:
        return False
    
    elif cmd == 'help':
        print_menu()
    
    elif cmd == 'check':
        rffc.check_device_id()
    
    elif cmd == 'read' and len(parts) == 1:
        rffc.read_all_registers()
    
    elif cmd == 'read' and len(parts) == 2:
        addr = int(parts[1], 16)
        value = rffc.read_register(addr)
        name = rffc.REGISTERS.get(addr, "Unknown")
        print(f"Register 0x{addr:02X} ({name}): 0x{value:04X} ({value:016b}) = {value}")
    
    elif cmd == 'write' and len(parts) == 3:
        addr = int(parts[1], 16)
        value = int(parts[2], 16)
        rffc.write_register(addr, value)
        print(f"✓ Written 0x{value:04X} to register 0x{addr:02X}")
    
    elif cmd == 'reset':
        rffc.reset_to_defaults()
    
    elif cmd == 'status':
        rffc.get_status_summary()
    
    elif cmd == 'freq' and len(parts) >= 2:
        freq = float(parts[1])
        path = int(parts[2]) if len(parts) > 2 else 1
        rffc.set_frequency(freq, path)
    
    elif cmd == 'enable' and len(parts) == 2:
        path = int(parts[1])
        rffc.enable_output(path, True)
    
    elif cmd == 'disable' and len(parts) == 2:
        path = int(parts[1])
        rffc.enable_output(path, False)
    
    elif cmd == 'cal':
        rffc.calibrate_vco()
    
    else:
        print("Unknown command. Type 'help' for available commands.")
    
    return True


def main():
    """Main console loop"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='RFFC5071 RF Synthesizer Control (3-wire GPIO bit-bang)',
        epilog='If no commands are provided, starts interactive console mode.'
    )
    parser.add_argument('--enx', type=int, default=27,
                        help='GPIO pin for ENX (enable/latch, default: 27)')
    parser.add_argument('--sclk', type=int, default=17,
                        help='GPIO pin for SCLK (clock, default: 17)')
    parser.add_argument('--sdata', type=int, default=4,
                        help='GPIO pin for SDATA (data, default: 4)')
    parser.add_argument('--resetx', type=int, default=None,
                        help='GPIO pin for RESETX (optional)')
    parser.add_argument('--enbl', type=int, default=None,
                        help='GPIO pin for ENBL (optional)')
    parser.add_argument('-r', '--ref-freq', type=float, default=50.0,
                        help='Reference frequency in MHz (default: 50.0)')
    parser.add_argument('command', nargs='*',
                        help='Command to execute (e.g., check, freq 1000, read, status)')
    
    args = parser.parse_args()
    
    # Initialize device
    try:
        rffc = RFFC5071(
            enx_pin=args.enx,
            sclk_pin=args.sclk,
            sdata_pin=args.sdata,
            ref_freq=args.ref_freq,
            resetx_pin=args.resetx,
            enbl_pin=args.enbl
        )
    except Exception as e:
        print(f"Failed to initialize RFFC5071: {e}")
        print("Make sure you have RPi.GPIO installed: pip3 install RPi.GPIO")
        print("And run as root or add user to gpio group")
        return 1
    
    try:
        # If command provided as arguments, execute and exit
        if args.command:
            cmd_input = ' '.join(args.command)
            try:
                execute_command(rffc, cmd_input)
                return 0
            except ValueError as e:
                print(f"✗ Invalid value: {e}")
                return 1
            except Exception as e:
                print(f"✗ Error: {e}")
                return 1
        
        # Otherwise, start interactive mode
        print("\nRFFC5071 RF Synthesizer Control")
        print("================================\n")
        print_menu()
        
        # Main command loop
        while True:
            try:
                cmd_input = input("\nrffc> ").strip()
                
                if not execute_command(rffc, cmd_input):
                    break
                
            except ValueError as e:
                print(f"✗ Invalid value: {e}")
            except KeyboardInterrupt:
                print("\nInterrupted")
                break
            except Exception as e:
                print(f"✗ Error: {e}")
    
    finally:
        rffc.close()
        if not args.command:  # Only print goodbye in interactive mode
            print("\nGoodbye!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
