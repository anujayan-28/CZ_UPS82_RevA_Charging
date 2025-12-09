import time
import csv
import serial
import pyvisa
from datetime import datetime
from pyvisa.constants import StopBits, Parity

# -------- Test Parameters --------
STOP_VOLTAGE = 8.3             # Stop logging when DUT reaches this voltage
SET_VOLTAGE = 12.0             # SPE output voltage
SET_CURRENT = 2.0              # Current limit in amps
LOG_INTERVAL = 10              # seconds (RTC aligned)
CSV_FILE = "charging_log.csv"

WT_COM = "COM14"
SPE_COM = "ASRL6::INSTR"


# ================================
# WT310E Functions
# ================================
def connect_wt310e(com=WT_COM):
    try:
        ser = serial.Serial(
            port=com,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )
        time.sleep(1)
        print(f"✅ WT310E Connected on {com}")
        return ser
    except Exception as e:
        print(f"❌ WT310E Serial Error: {e}")
        return None


def wt_write(ser, cmd):
    ser.write((cmd + "\r\n").encode())


def wt_query(ser, cmd):
    wt_write(ser, cmd)
    return ser.readline().decode().strip()


def setup_wt310e(ser):
    wt_write(ser, "*RST")
    time.sleep(1)
    wt_write(ser, ":INPut:MODE DC")
    wt_write(ser, ":INPut:WIRing P1W2")
    wt_write(ser, ":INPut:VOLTage:RANGe:AUTO ON")
    wt_write(ser, ":INPut:CURRent:RANGe:AUTO ON")
    wt_write(ser, ":FORM:ELEM VOLT,CURR,POW")
    print("⚙️ WT310E Ready")


def read_wt310e(ser):
    time.sleep(0.4)         # ← WT310E needs processing time per query
    v = float(wt_query(ser, ":NUM:NORM:VAL? 1"))
    time.sleep(0.1)
    i = float(wt_query(ser, ":NUM:NORM:VAL? 2"))
    time.sleep(0.1)
    p = float(wt_query(ser, ":NUM:NORM:VAL? 3"))
    return v, i, p


# ================================
# SPE6103 Functions
# ================================
def connect_spe6103():
    rm = pyvisa.ResourceManager()
    try:
        print("[INFO] Connecting SPE6103 on CH340...")
        dc = rm.open_resource(SPE_COM)
        dc.baud_rate = 115200
        dc.data_bits = 8
        dc.stop_bits = StopBits.one
        dc.paritary = Parity.none
        dc.read_termination = "\r\n"
        dc.write_termination = "\r\n"

        print(f"Power Supply ID: {dc.query('*IDN?').strip()}")
        print("✅ SPE6103 Connected")
        return rm, dc
    except Exception as e:
        print(f"❌ SPE6103 Connection Error: {e}")
        return None, None


# ================================
# Real-time 10-second alignment
# ================================
def wait_until_next_10sec_tick():
    now = datetime.now()
    sec = now.second
    remainder = sec % LOG_INTERVAL
    wait = LOG_INTERVAL - remainder
    if wait == LOG_INTERVAL:
        wait = 0
    time.sleep(wait)


# ================================
# Logging
# ================================
def log_row(ser):
    time.sleep(1.0)   # ← VERY IMPORTANT: stabilize WT310E before reading
    v, i, p = read_wt310e(ser)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, v, i, p])

    print(f"{timestamp} | V={v:.3f} | I={i:.3f} | P={p:.3f}")
    return v


# ================================
# MAIN EXECUTION
# ================================
ser = connect_wt310e()
setup_wt310e(ser)

rm, dc = connect_spe6103()

dc.write(f"VOLT {SET_VOLTAGE:.2f}")
dc.write("OUTP ON")

time.sleep(2)
print(f"[OK] DC Source ENABLED → {SET_VOLTAGE:.2f}V\n")

# CSV
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Timestamp", "Voltage(V)", "Current(A)", "Power(W)"])

print("📄 Logging started (first reading immediate)...\n")


# FIRST READING IMMEDIATELY
voltage = log_row(ser)

try:
    while voltage < STOP_VOLTAGE:

        wait_until_next_10sec_tick()
        voltage = log_row(ser)

        if voltage >= STOP_VOLTAGE:
            print(f"\n✅ Stop Condition → Voltage: {voltage:.3f}V")
            break

except KeyboardInterrupt:
    print("⏹️ User stopped logging")

finally:
    print("\n🔄 Shutting down...")

    try:
        dc.write("OUTP OFF")
        print("🔌 DC OFF")
    except:
        pass

    try:
        dc.close()
        rm.close()
        print("✅ SPE Closed")
    except:
        pass

    try:
        ser.close()
        print("✅ WT310E Closed")
    except:
        pass

    print("📄 CSV Saved:", CSV_FILE)
