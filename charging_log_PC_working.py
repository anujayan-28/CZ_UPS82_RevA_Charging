#!/usr/bin/env python3

import time
import csv
import pyvisa
import os
from datetime import datetime
import matplotlib.pyplot as plt
from pyvisa.constants import StopBits, Parity

# =====================================================
# ----------- Test Parameters -------------------------
# =====================================================

STOP_VOLTAGE = 8.35
SET_VOLTAGE = 12.0
SET_CURRENT = 2.0
LOG_INTERVAL = 1       # changed to 1 sec so you see graph movement
STABILIZING_TIME = 0.5

CSV_FILE_TEMPLATE = "charging_log_{timestamp}.csv"

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
# ----------- WT310E Functions ------------------------
# =====================================================

def detect_wt310e(rm):
    """Return first USBTMC resource that responds as Yokogawa."""
    for res in rm.list_resources():
        if "USB" not in res:
            continue
        try:
            inst = rm.open_resource(res)
            inst.timeout = 3000
            inst.write_termination = '\n'
            inst.read_termination = '\n'
            idn = inst.query("*IDN?")
            if "YOKOGAWA" in idn or "WT310" in idn:
                print(f"★ WT310E detected: {res}")
                return inst
        except:
            pass
    return None


def setup_wt310e(wt):
    wt.write("*RST")
    time.sleep(1)
    wt.write(":INPUT:MODE DC")
    wt.write(":INPUT:WIRING P1W2")
    wt.write(":INPUT:VOLTAGE:RANGE:AUTO ON")
    wt.write(":INPUT:CURRENT:RANGE:AUTO ON")
    wt.write(":NUM:ITEM1 U,1")
    wt.write(":NUM:ITEM2 I,1")
    wt.write(":NUM:ITEM3 P,1")
    wt.write(":NUM:NUMB 3")
    wt.write(":NUM:FORM ASCII")
    print("★ WT310E Ready ✓")


def read_wt310e(wt):
    wt.write(":NUM:VAL?")
    raw = wt.read().strip()
    parts = raw.split(",")
    v = float(parts[0])
    i = float(parts[1])
    p = float(parts[2])
    return v, i, p


# =====================================================
# ----------- SPE6103 Detection -----------------------
# =====================================================

def detect_spe6103(rm):
    """Find SPE6103 on serial (ASRLxx::INSTR)."""
    for res in rm.list_resources():
        if res.startswith("ASRL") and res.endswith("INSTR"):
            try:
                print(f"Opening DC Source on {res}")
                dc = rm.open_resource(res)

                dc.baud_rate = 115200
                dc.data_bits = 8
                dc.stop_bits = StopBits.one
                dc.parity = Parity.none
                dc.write_termination = "\r\n"
                dc.read_termination = "\r\n"

                idn = dc.query("*IDN?")
                print(f"*IDN? -> {idn}")

                if "SPE" in idn or "6103" in idn:
                    print("★ SPE6103 Ready ✓")
                    return dc

                dc.close()
            except Exception as e:
                print(f"⚠ Error opening {res}: {e}")

    return None


# =====================================================
# ----------------- Main ------------------------------
# =====================================================

def main():

    print("🔎 Detecting instruments...\n")

    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()

    print("VISA resources found:")
    for r in resources:
        print("  ", r)
    print()

    # ---- WT310E ----
    wt = detect_wt310e(rm)
    if not wt:
        print("✖ WT310E not found. Exiting.")
        return
    setup_wt310e(wt)

    # ---- DC Source ----
    dc = detect_spe6103(rm)
    if not dc:
        print("✖ DC Source (SPE6103) not connected. Exiting.")
        return

    # Enable output
    dc.write(f"VOLT {SET_VOLTAGE:.2f}")
    dc.write(f"CURR {SET_CURRENT:.2f}")
    dc.write("OUTP ON")
    print(f"[OK] DC Source ENABLED → {SET_VOLTAGE} V / {SET_CURRENT} A\n")
    time.sleep(STABILIZING_TIME)

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = CSV_FILE_TEMPLATE.format(timestamp=run_timestamp)

    # Write CSV headers
    with open(csv_file, "w", newline="") as f:
        csv.writer(f).writerow(CSV_HEADERS)

    print(f"📝 Logging every {LOG_INTERVAL}s\n")

    # =====================================================
    # ----------------- Plot Setup ------------------------
    # =====================================================

    plt.ion()
    fig, ax = plt.subplots()

    volt_line, = ax.plot([], [], label="Output Voltage (V)")
    amp_line, = ax.plot([], [], label="Output Current (A)")
    #pow_line, = ax.plot([], [], label="Output Power (W)")

    ax.set_xlabel("Elapsed Time (s)")
    ax.set_ylabel("Output Values")
    ax.legend()

    time_arr = []
    volt_arr = []
    amp_arr = []
    #pow_arr = []

    def update_plot(t, v, a, p):
        time_arr.append(t)
        volt_arr.append(v)
        amp_arr.append(a)
        #pow_arr.append(p)

        volt_line.set_data(time_arr, volt_arr)
        amp_line.set_data(time_arr, amp_arr)
        #pow_line.set_data(time_arr, pow_arr)

        ax.relim()
        ax.autoscale_view()

        plt.draw()
        plt.pause(0.01)

    # =====================================================
    # ----------------- Logging Loop ---------------------
    # =====================================================

    start_time = time.time()

    try:
        while True:
            # Read WT310E
            Ov, Oc, Op = read_wt310e(wt)

            # Read DC Source
            Iv = float(dc.query("MEAS:VOLT?"))
            Ic = float(dc.query("MEAS:CURR?"))
            Ip = float(dc.query("MEAS:POW?"))

            OutCurrent = abs(Oc)
            OutPower = abs(Op)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(csv_file, "a", newline="") as f:
                csv.writer(f).writerow([timestamp, Iv, Ic, Ip, Ov, OutCurrent, OutPower])

            elapsed = time.time() - start_time
            update_plot(elapsed, Ov, OutCurrent, OutPower)

            print(f"{timestamp} | Out: {Ov:.3f}V  {OutCurrent:.3f}A  {OutPower:.3f}W")

            if Ov >= STOP_VOLTAGE:
                print(f"\n✔ Stop condition reached → {Ov:.3f} V")
                break

            time.sleep(LOG_INTERVAL)

    except KeyboardInterrupt:
        print("\n⏹ Logging stopped by user")

    finally:
        print("\n🔧 Shutting down...")

        try:
            dc.write("OUTP OFF")
            print("DC Output OFF")
        except:
            pass

        try:
            wt.close()
            print("WT310E Closed")
        except:
            pass

        try:
            dc.close()
            rm.close()
            print("SPE6103 Closed")
        except:
            pass

        plt.ioff()
        plt.close(fig)

        print(f"\n✔ CSV Saved: {csv_file}\n")


if __name__ == "__main__":
    main()
