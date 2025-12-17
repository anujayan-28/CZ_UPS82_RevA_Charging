#!/usr/bin/env python3



import time

import csv

import os

from datetime import datetime

import matplotlib.pyplot as plt

from pyvisa.constants import StopBits, Parity



from wt310e_driver import WT310E    # <--- New unified driver



# =======================================================

# USER PARAMETERS

# =======================================================



STOP_VOLTAGE = 8.35

SET_VOLTAGE = 12.0

SET_CURRENT = 2.0

LOG_INTERVAL = 3

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





# =======================================================

# DETECT SPE6103 (DC SOURCE)

# =======================================================

import pyvisa



def detect_spe6103(rm):

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

                print(f"*IDN? â†’ {idn}")



                if "SPE" in idn or "6103" in idn:

                    print("â˜… SPE6103 Ready âœ“")

                    return dc



                dc.close()

            except Exception as e:

                print(f"âš  Error opening {res}: {e}")



    return None







# =======================================================

# MAIN PROGRAM

# =======================================================



def main():



    print("\nðŸ”Ž Detecting Instruments...\n")



    # ---- WT310E ----

    wt = WT310E()

    if not wt.connect():

        print("âœ– WT310E is not detected. Exiting.")

        return

    wt.setup()



    # ---- SPE6103 (DC Source) ----

    rm = pyvisa.ResourceManager()

    dc = detect_spe6103(rm)

    if not dc:

        print("âœ– DC Source not found. Exiting.")

        return



    # Enable output

    dc.write(f"VOLT {SET_VOLTAGE:.2f}")

    dc.write(f"CURR {SET_CURRENT:.2f}")

    dc.write("OUTP ON")

    print(f"[OK] DC Source ENABLED â†’ {SET_VOLTAGE} V / {SET_CURRENT} A\n")

    time.sleep(STABILIZING_TIME)



    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_file = CSV_FILE_TEMPLATE.format(timestamp=run_timestamp)

    graph_file = csv_file.replace(".csv", ".png")



    with open(csv_file, "w", newline="") as f:

        csv.writer(f).writerow(CSV_HEADERS)



    print(f"ðŸ“ Logging every {LOG_INTERVAL}s\n")



    # =======================================================

    # REALTIME PLOT

    # =======================================================

    plt.ion()

    fig, ax = plt.subplots()



    volt_line, = ax.plot([], [], label="Output Voltage (V)")

    amp_line, = ax.plot([], [], label="Output Current (A)")



    ax.set_xlabel("Elapsed Time (s)")

    ax.set_ylabel("Output Values")

    ax.legend()



    time_arr = []

    volt_arr = []

    amp_arr = []



    def update_plot(t, v, a):

        time_arr.append(t)

        volt_arr.append(v)

        amp_arr.append(a)



        volt_line.set_data(time_arr, volt_arr)

        amp_line.set_data(time_arr, amp_arr)



        ax.relim()

        ax.autoscale_view()

        plt.draw()

        plt.pause(0.01)



    # =======================================================

    # MAIN LOOP

    # =======================================================

    start_time = time.time()



    try:

        while True:

            # Read WT310E

            Ov, Oc, Op = wt.read()



            # Make Output always positive

            Oc = abs(Oc)

            Op = abs(Op)



            # Read DC source

            Iv = float(dc.query("MEAS:VOLT?"))

            Ic = float(dc.query("MEAS:CURR?"))

            Ip = float(dc.query("MEAS:POW?"))



            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")



            with open(csv_file, "a", newline="") as f:

                csv.writer(f).writerow(

                    [timestamp, Iv, Ic, Ip, Ov, Oc, Op]

                )



            elapsed = time.time() - start_time

            update_plot(elapsed, Ov, Oc)



            print(f"{timestamp} | Out = {Ov:.3f} V  {Oc:.3f} A  {Op:.3f} W")



            if Ov >= STOP_VOLTAGE:

                print(f"\nâœ” Stop condition reached â†’ {Ov:.3f} V")

                break



            time.sleep(LOG_INTERVAL)



    except KeyboardInterrupt:

        print("\nâ¹ Logging stopped by user")



    finally:

        print("\nðŸ”§ Shutting down...")



        try:

            dc.write("OUTP OFF")

            print("DC Output OFF")

        except:

            pass



        wt.close()



        try:

            dc.close()

            rm.close()

        except:

            pass



        # ? Save graph at the end WITHOUT stopping live display during run

        fig.savefig(graph_file, dpi=300, bbox_inches="tight")

        

        plt.ioff()

        plt.close(fig)



        print(f"\nâœ” CSV Saved: {csv_file}\n")

        print(f"âœ” Graph Saved: {graph_file}\n")





if __name__ == "__main__":

    main()
