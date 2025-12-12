#!/usr/bin/env python3
import sys
import time

USE_PYVISA = False
USE_USBTMC = False

# Try VISA backend
try:
    import pyvisa
    USE_PYVISA = True
except ImportError:
    pass

# Try USBTMC fallback
try:
    import usbtmc
    USE_USBTMC = True
except ImportError:
    pass


class WT310E:
    def __init__(self):
        self.backend = None
        self.inst = None
        self.rm = None

    # ------------------------------------------------------
    # AUTO-DETECT CONNECTION METHOD
    # ------------------------------------------------------
    def connect(self):
        # 1) Try VISA first (Windows PC)
        if USE_PYVISA:
            try:
                self.rm = pyvisa.ResourceManager()
                for res in self.rm.list_resources():
                    if "USB" in res:
                        inst = self.rm.open_resource(res)
                        inst.write_termination = "\n"
                        inst.read_termination = "\n"

                        idn = inst.query("*IDN?")
                        if "YOKOGAWA" in idn:
                            self.inst = inst
                            self.backend = "VISA"
                            print(f"★ WT310E connected via VISA → {res}")
                            return True
            except Exception as e:
                print("VISA detection failed:", e)

        # 2) Try USBTMC (Linux Raspberry Pi)
        if USE_USBTMC:
            try:
                inst = usbtmc.Instrument("USB::0x0B21::0x0025::INSTR")
                idn = inst.ask("*IDN?")
                if "YOKOGAWA" in idn:
                    self.inst = inst
                    self.backend = "USBTMC"
                    print("★ WT310E connected via USBTMC (/dev/usbtmc*)")
                    return True
            except Exception as e:
                print("USBTMC detection failed:", e)

        print("✖ WT310E not found.")
        return False

    # ------------------------------------------------------
    # SETUP INSTRUMENT
    # ------------------------------------------------------
    def setup(self):
        w = self.inst.write

        if self.backend == "VISA":
            w("*RST")
            time.sleep(1)
            w(":INPUT:MODE DC")
            w(":INPUT:WIRING P1W2")
            w(":NUM:ITEM1 U,1")
            w(":NUM:ITEM2 I,1")
            w(":NUM:ITEM3 P,1")
            w(":NUM:NUMB 3")
            w(":NUM:FORM ASCII")

        else:  # USBTMC
            w("*RST\n")
            time.sleep(1)
            w(":INPUT:MODE DC\n")
            w(":INPUT:WIRING P1W2\n")
            w(":NUM:ITEM1 U,1\n")
            w(":NUM:ITEM2 I,1\n")
            w(":NUM:ITEM3 P,1\n")
            w(":NUM:NUMB 3\n")
            w(":NUM:FORM ASCII\n")

        print("★ WT310E is ready ✓")

    # ------------------------------------------------------
    # READ VALUES (V, A, W)
    # ------------------------------------------------------
    def read(self):
        if self.backend == "VISA":
            raw = self.inst.query(":NUM:VAL?")
        else:
            self.inst.write(":NUM:VAL?\n")
            raw = self.inst.read()

        parts = raw.strip().split(",")
        v = float(parts[0])
        i = float(parts[1])
        p = float(parts[2])
        return v, i, p

    # ------------------------------------------------------
    # CLOSE
    # ------------------------------------------------------
    def close(self):
        try:
            self.inst.close()
        except:
            pass
        try:
            if self.rm:
                self.rm.close()
        except:
            pass
