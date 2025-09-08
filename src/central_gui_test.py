import tkinter as tk
from tkinter import ttk
import threading, queue, time, random
from GUI import WienerGUI

# -------------------------
# Global thread control
# -------------------------
data_queue = queue.Queue()
stop_event = threading.Event()

# -------------------------
# Dummy Serial Monitor GUI
# -------------------------
class SerialMonitorGUI(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.temp_var = tk.StringVar(value="Temp: -- °C")
        self.pres_var = tk.StringVar(value="Pressure: -- bar")

        ttk.Label(self, textvariable=self.temp_var).pack(pady=5)
        ttk.Label(self, textvariable=self.pres_var).pack(pady=5)

    def update_from_data(self, data):
        if "temp" in data:
            self.temp_var.set(f"Temp: {data['temp']:.2f} °C")
        if "pressure" in data:
            self.pres_var.set(f"Pressure: {data['pressure']:.2f} bar")

# -------------------------
# Serial worker (dummy)
# -------------------------
def serial_poll_worker(name, interval=2):
    while not stop_event.is_set():
        val = {
            "type": "serial",
            "temp": random.uniform(20, 25),
            "pressure": random.uniform(1.0, 1.2),
        }
        data_queue.put(val)
        time.sleep(interval)

# -------------------------
# Import your WienerGUI here
# (this is the one we built earlier with set voltage, Imeas, Ramp buttons etc.)
# For now I'll stub a minimal version so it compiles.
'''
class WienerGUI(ttk.Frame):
    def __init__(self, parent, wiener_obj=None):
        super().__init__(parent)
        self.tree = ttk.Treeview(self, columns=("Ch", "Vset", "Vmeas", "Imeas"), show="headings")
        for col in ("Ch", "Vset", "Vmeas", "Imeas"):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=80)
        self.tree.pack(expand=True, fill="both")
        for ch in range(8):
            self.tree.insert("", "end", iid=ch, values=(ch, "", "", ""))

    def update_from_data(self, data):
        if "ch" in data:
            self.tree.item(data["ch"], values=(data["ch"], data["vset"], data["vmeas"], data["imeas"]))
# -------------------------
'''
# -------------------------
# Wiener worker (dummy values for now)
# -------------------------
def wiener_poll_worker(name, interval=3):
    while not stop_event.is_set():
        for ch in range(8):
            val = {
                "type": "wiener",
                "ch": ch,
                "vset": 120.0 if ch % 2 == 0 else 0.0,
                "vmeas": 120.0 if ch % 2 == 0 else 0.0 + random.uniform(-0.5, 0.5),
                "imeas": random.uniform(0.0, 0.05),
            }
            data_queue.put(val)
        time.sleep(interval)

# -------------------------
# Central DAQ GUI
# -------------------------
class CentralDAQ(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Central DAQ GUI")

        # Frame for hardware selection
        self.device_frame = ttk.LabelFrame(self, text="Devices")
        self.device_frame.pack(side="top", fill="x", padx=5, pady=5)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both")

        # Dicts to keep track of devices
        self.device_vars = {
            "Wiener": tk.BooleanVar(value=False),
            "Serial": tk.BooleanVar(value=False),
        }
        self.device_tabs = {}
        self.device_threads = {}

        # Add checkboxes
        for name, var in self.device_vars.items():
            cb = ttk.Checkbutton(
                self.device_frame,
                text=name,
                variable=var,
                command=lambda n=name: self.toggle_device(n),
            )
            cb.pack(side="left", padx=10, pady=5)

        # Poll queue
        self.after(500, self.check_queue)

    def toggle_device(self, name):
        """Enable or disable a device."""
        if self.device_vars[name].get():
            # Enable device
            if name == "Wiener":
                tab = WienerGUI(self.notebook)
                self.device_tabs[name] = tab
                self.notebook.add(tab, text=name)
                t = threading.Thread(target=wiener_poll_worker, args=(name,), daemon=True)
                self.device_threads[name] = t
                t.start()
            elif name == "Serial":
                tab = SerialMonitorGUI(self.notebook)
                self.device_tabs[name] = tab
                self.notebook.add(tab, text=name)
                t = threading.Thread(target=serial_poll_worker, args=(name,), daemon=True)
                self.device_threads[name] = t
                t.start()
        else:
            # Disable device
            if name in self.device_tabs:
                tab = self.device_tabs.pop(name)
                self.notebook.forget(tab)
            if name in self.device_threads:
                # no direct way to kill thread; rely on stop_event if shutting down
                self.device_threads.pop(name)

    def check_queue(self):
        """Update only the selected tab."""
        try:
            while True:
                data = data_queue.get_nowait()
                current_tab = self.notebook.tab(self.notebook.select(), "text") if self.notebook.tabs() else None
                if current_tab and current_tab in self.device_tabs:
                    if data["type"] == "serial" and current_tab == "Serial":
                        self.device_tabs["Serial"].update_from_data(data)
                    elif data["type"] == "wiener" and current_tab == "Wiener":
                        self.device_tabs["Wiener"].update_from_data(data)
        except queue.Empty:
            pass
        self.after(500, self.check_queue)

# -------------------------
# Main entry point
# -------------------------
if __name__ == "__main__":
    app = CentralDAQ()
    app.mainloop()
    stop_event.set()
