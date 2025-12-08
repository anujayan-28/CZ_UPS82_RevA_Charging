#!/usr/bin/env python3

import time

import csv

import serial

import pyvisa

import os

from datetime import datetime

from pyvisa.constants import StopBits, Parity

import matplotlib.pyplot as plt



# =====================================================

# ----------- Test Parameters (Editable Section) -------

# =====================================================

STOP_VOLTAGE = 8.35             # Stop logging when DUT reaches this voltage

SET_VOLTAGE = 12.0              # SPE output voltage

SET_CURRENT = 2.0              # Current limit in amps

LOG_INTERVAL = 10               # seconds between readings

STABILIZING_TIME = 0.5          # wait before sampling after switching

CSV_FILE_TEMPLATE = "/home/harsha/newUPS-8_2/charging_log_{timestamp}.csv"



CSV_HEADERS = [

    "Timestamp",

    "Input_Voltage(V)",

    "Input_Current(A)",

    "Input_Power(W)",

    "Output_Voltage(V)",

    "Output_Current(A)",

    "Output_Power(W)"

]



# =====================================================

# ----------- Helper Functions ------------------------

# =====================================================

def detect_serial_devices():

    """Return a list of /dev/ttyUSB* devices available"""

    devices = [f"/dev/{d}" for d in os.listdir("/dev") if d.startswith("ttyUSB")]

    devices.sort()

    # devices = ["/dev/ttyUSB4"]

    return devices





def detect_wt310e():

    """Try to detect WT310E by sending *IDN? query"""

    for dev in detect_serial_devices():

        try:

            ser = serial.Serial(dev, 9600, timeout=1)

            print(f"âœ… WT310E detected on {dev}")

            ser.write(b"*IDN?\r\n")

            time.sleep(0.3)

            resp = ser.readline().decode(errors="ignore").strip()

            ser.close()

            if "YOKOGAWA" in resp or "WT310" in resp:

                print(f"âœ… WT310E detected on {dev}")

                return dev

        except Exception:

            pass

    return None





def detect_spe6103():

    """Find SPE6103 in VISA resources (CH340 USB interface)"""

    rm = pyvisa.ResourceManager()

    resources = rm.list_resources()

    for res in resources:

        if "ASRL" in res and "INSTR" in res:

            try:

                dc = rm.open_resource(res)

                dc.baud_rate = 115200

                dc.data_bits = 8

                dc.stop_bits = StopBits.one

                dc.parity = Parity.none

                dc.read_termination = "\r\n"

                dc.write_termination = "\r\n"

                idn = dc.query("*IDN?").strip()

                if "SPE" in idn or "6103" in idn:

                    print(f"âœ… SPE6103 detected at {res}")

                    return rm, dc

                dc.close()

            except Exception:

                pass

    return None, None





def connect_wt310e(com):

    try:

        ser = serial.Serial(

            port=com,

            baudrate=19200,

            bytesize=serial.EIGHTBITS,

            parity=serial.PARITY_NONE,

            stopbits=serial.STOPBITS_ONE,

            timeout=2  # allow a bit more time for WT310E to respond

        )

        time.sleep(1)

        print(f"âœ… WT310E Connected on {com}")

        return ser

    except Exception as e:

        print(f"âŒ WT310E Serial Error: {e}")

        return None





def wt_write(ser, cmd):

    ser.write((cmd + "\r\n").encode())





def wt_query(ser, cmd):

    wt_write(ser, cmd)

    return ser.readline().decode(errors="ignore").strip()





def setup_wt310e(ser):

    wt_write(ser, "*RST")

    time.sleep(1)

    wt_write(ser, ":INPut:MODE DC")

    wt_write(ser, ":INPut:WIRing P1W2")

    wt_write(ser, ":INPut:VOLTage:RANGe:AUTO ON")

    wt_write(ser, ":INPut:CURRent:RANGe:AUTO ON")

    wt_write(ser, ":FORM:ELEM VOLT,CURR,POW")

    print("âš™ï¸ WT310E Ready âœ…")

    time.sleep(0.5)





def read_wt310e(ser, retries=5):

    """Read V, I, P from WT310E with basic retry + parse protection."""

    last_error = None

    for attempt in range(1, retries + 1):

        try:

            time.sleep(STABILIZING_TIME)

            try:

                ser.reset_input_buffer()

                ser.reset_output_buffer()

            except Exception:

                # Not fatal; continue if buffer reset is unsupported

                pass

            # Single query is more reliable than 3 separate ones

            raw_line = ""

            # Use wt_query (writes and reads) up to 3 times to skip occasional blank replies

            for _ in range(3):

                raw_line = wt_query(ser, ":NUM:NORM:VAL?")

                if raw_line:

                    break

                time.sleep(0.05)

            if not raw_line:

                raise ValueError("empty response line")

            parts = [p.strip() for p in raw_line.split(",") if p.strip() != ""]

            if len(parts) < 3:

                raise ValueError(f"incomplete response: {raw_line!r}")

            v, i, p = (float(parts[0]), float(parts[1]), float(parts[2]))

            print(f"ðŸ” WT310E Readings â†’ V: {v:.3f} V, I: {i:.3f} A, P: {p:.3f} W")

            return v, i, p

        except ValueError as e:

            last_error = f"parse error attempt {attempt}/{retries}: {e}"

            print(f"[WARN] WT310E read error: {last_error}")

            time.sleep(0.2)

        except Exception as e:

            last_error = f"comm error attempt {attempt}/{retries}: {e}"

            print(f"[WARN] WT310E read error: {last_error}")

            time.sleep(0.2)

    raise RuntimeError(last_error or "Unknown WT310E read error")





# =====================================================

# ----------- Main Logging Function -------------------

# =====================================================

def main():

    print("ðŸ” Detecting instruments...\n")



    # WT310E setup

    wt_port = detect_wt310e()

    time.sleep(0.5)

    ser = connect_wt310e(wt_port) if wt_port else None

    if ser:

        setup_wt310e(ser)



    # SPE6103 setup

    rm, dc = detect_spe6103()

    time.sleep(0.5)

    if not dc:

        print("âŒ DC Source not connected. Exiting.")

        return



    # Configure DC Source

    dc.write(f"VOLT {SET_VOLTAGE:.2f}")

    dc.write(f"CURR {SET_CURRENT:.2f}")

    dc.write("OUTP ON")

    print(f"[OK] DC Source ENABLED â†’ {SET_VOLTAGE:.2f} V / {SET_CURRENT:.2f} A")

    print(f"â³ Waiting {STABILIZING_TIME}s for system to stabilize...\n")

    time.sleep(STABILIZING_TIME)



    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_file = CSV_FILE_TEMPLATE.format(timestamp=run_timestamp)



    # Prepare CSV

    with open(csv_file, "w", newline="") as f:

        csv.writer(f).writerow(CSV_HEADERS)

    print(f"ðŸ“„ Logging every {LOG_INTERVAL}s ...\n")



    # Real-time plotting setup

    plt.ion()

    fig, ax = plt.subplots()

    voltage_line, = ax.plot([], [], label="Output Voltage (V)", color="tab:blue")

    current_line, = ax.plot([], [], label="Output Current (A)", color="tab:orange")

    ax.set_xlabel("Elapsed Time (s)")

    ax.set_ylabel("Output Values")

    ax.legend()

    time_points = []

    voltage_points = []

    current_points = []



    def update_plot(elapsed, voltage, current):

        time_points.append(elapsed)

        voltage_points.append(voltage)

        current_points.append(current)

        voltage_line.set_data(time_points, voltage_points)

        current_line.set_data(time_points, current_points)

        ax.relim()

        ax.autoscale_view()

        plt.draw()

        plt.pause(0.01)



    def log_row():

        Ov, Oc, Op = read_wt310e(ser)

        Iv = float(dc.query("MEAS:VOLT?"))

        Ic = float(dc.query("MEAS:CURR?"))

        Ip = float(dc.query("MEAS:POW?"))

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        output_current = abs(Oc)

        output_power = abs(Op)

        with open(csv_file, "a", newline="") as f:

            csv.writer(f).writerow([timestamp, Iv, Ic, Ip, Ov, output_current, output_power])

        elapsed = time.time() - start_time

        update_plot(elapsed, Ov, output_current)

        print(f"{timestamp} | Out: {Ov:.3f}V {output_current:.3f}A {output_power:.3f}W")

        return Ov



    # --- Real-Time Non-blocking Logging Loop ---

    start_time = time.time()

    next_log_time = start_time

    voltage = 0.0



    try:

        while True:

            now = time.time()



            if now >= next_log_time:

                voltage = log_row()

                next_log_time += LOG_INTERVAL



                if voltage >= STOP_VOLTAGE:

                    print(f"\nâœ… Stop Condition Reached â†’ Voltage: {voltage:.3f} V")

                    break



            time.sleep(0.1)  # small yield to CPU



    except KeyboardInterrupt:

        print("\nâ¹ï¸ Logging stopped by user")



    finally:

        print("\nðŸ”„ Shutting down ...")

        try:

            dc.write("OUTP OFF")

            print("ðŸ”Œ DC Output OFF")

        except:

            pass

        try:

            dc.close()

            rm.close()

            print("âœ… SPE6103 Closed")

        except:

            pass

        try:

            ser.close()

            print("âœ… WT310E Serial Closed")

        except:

            pass

        try:

            plt.ioff()

            plt.close(fig)

        except:

            pass



        print(f"\nâœ… Ready for next test â€” No USB unplug required ðŸ‘")

        print(f"ðŸ“„ CSV Saved: {csv_file}")





# =====================================================

# ---------------- Entry Point ------------------------

# =====================================================

if __name__ == "__main__":

    main()

