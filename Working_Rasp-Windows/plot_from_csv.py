import pandas as pd
import matplotlib.pyplot as plt

# -------------------------------------------------
# USER INPUT
# -------------------------------------------------
CSV_FILE = "charging_log_20251215_142555.csv"
SAVE_GRAPH = True   # Set False if you only want display

# -------------------------------------------------
# LOAD CSV
# -------------------------------------------------
df = pd.read_csv(CSV_FILE)

# Convert Timestamp to datetime
df["Timestamp"] = pd.to_datetime(df["Timestamp"])

# -------------------------------------------------
# PLOT
# -------------------------------------------------
plt.figure(figsize=(10, 5))

plt.plot(df["Timestamp"], df["Output_Voltage(V)"], label="Output Voltage (V)")
plt.plot(df["Timestamp"], df["Output_Current(A)"], label="Output Current (A)")

plt.xlabel("Time")
plt.ylabel("Value")
plt.title("Output Voltage & Current vs Time")
plt.legend()
plt.grid(True)

plt.xticks(rotation=45)
plt.tight_layout()

# -------------------------------------------------
# SAVE GRAPH (same name as CSV)
# -------------------------------------------------
if SAVE_GRAPH:
    graph_file = CSV_FILE.replace(".csv", ".png")
    plt.savefig(graph_file, dpi=300, bbox_inches="tight")
    print(f"âœ” Graph Saved: {graph_file}")

# -------------------------------------------------
# SHOW
# -------------------------------------------------
plt.show()