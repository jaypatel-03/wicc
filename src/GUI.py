import tkinter as tk
from tkinter import ttk
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor
import asyncio
import logging
from functools import wraps

from Wiener import Wiener

# --- Your existing Wiener class goes here (full definition unchanged) ---
# from utils import FloatOpaque, opaque_to_float, switch_to_int, LoggingFormat
# class Wiener: ...

# Replace with actual Wiener class import or paste full class above
# from your_wiener_module import Wiener

HOST = '10.179.59.29'
MIB_DIR = '/usr/share/snmp/mibs'
MIB_NAME = 'WIENER-CRATE-MIB'

class WienerGUI(ttk.Frame):
    def __init__(self, root):
        super().__init__(root)
        self.root = root
        # self.root.title("Wiener Crate HV/LV Controller")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True)

        self.hv_tab = ttk.Frame(self.notebook)
        self.lv_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.hv_tab, text="HV Channels")
        self.notebook.add(self.lv_tab, text="LV Channels")

        self.hv_entries = []
        self.lv_entries = []
        self.refresh_paused = False
        self.command_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=8)

        # Create Wiener device objects
        self.hv_wiener = Wiener(HOST, MIB_DIR, MIB_NAME, 'HV')
        self.lv_wiener = Wiener(HOST, MIB_DIR, MIB_NAME, 'LV')

        self.build_hv_tab()
        self.build_lv_tab()

        # Control buttons
        ctrl_frame = ttk.Frame(root)
        ctrl_frame.pack(fill='x', pady=5)
        all_off_btn = ttk.Button(ctrl_frame, text="All OFF", command=self.all_off)
        all_off_btn.pack(side='left', padx=5)
        clear_btn = ttk.Button(ctrl_frame, text="Clear Events", command=self.clear_all_events)
        clear_btn.pack(side='left', padx=5)
        power_on_btn = ttk.Button(ctrl_frame, text="Crate ON", command=lambda: self.queue_crate_power(True))
        power_on_btn.pack(side='left', padx=5)
        power_off_btn = ttk.Button(ctrl_frame, text="Crate OFF", command=lambda: self.queue_crate_power(False))
        power_off_btn.pack(side='left', padx=5)

        self.start_refresh_loop()

    def build_hv_tab(self):
        headers = ["Channel", "Vset", "Vmeas", "Status", "Apply"]
        for c, h in enumerate(headers):
            ttk.Label(self.hv_tab, text=h).grid(row=0, column=c)

        for i in range(8):
            row = []
            ttk.Label(self.hv_tab, text=f"HV Ch {i+1}").grid(row=i+1, column=0)
            vset = ttk.Entry(self.hv_tab, width=8)
            vset.grid(row=i+1, column=1)
            vmeas = ttk.Label(self.hv_tab, text="0.0")
            vmeas.grid(row=i+1, column=2)
            status = tk.Canvas(self.hv_tab, width=20, height=20)
            status.grid(row=i+1, column=3)
            apply_btn = ttk.Button(self.hv_tab, text="Apply", command=lambda ch=i+1, e=vset: self.queue_voltage_set(self.hv_wiener, ch, e))
            apply_btn.grid(row=i+1, column=4)
            vset.bind("<FocusIn>", self.pause_refresh)
            vset.bind("<FocusOut>", self.resume_refresh)
            vset.bind("<Return>", lambda event, ch=i+1, e=vset: self.queue_voltage_set(self.hv_wiener, ch, e))
            row.extend([vset, vmeas, status])
            self.hv_entries.append(row)

    def build_lv_tab(self):
        headers = ["Channel", "Vset", "Vmeas", "Iset", "Imeas", "Status", "Apply"]
        for c, h in enumerate(headers):
            ttk.Label(self.lv_tab, text=h).grid(row=0, column=c)

        for i in range(8):
            row = []
            ttk.Label(self.lv_tab, text=f"LV Ch {i+1}").grid(row=i+1, column=0)
            vset = ttk.Entry(self.lv_tab, width=8)
            vset.grid(row=i+1, column=1)
            vmeas = ttk.Label(self.lv_tab, text="0.0")
            vmeas.grid(row=i+1, column=2)
            iset = ttk.Entry(self.lv_tab, width=8)
            iset.grid(row=i+1, column=3)
            imeas = ttk.Label(self.lv_tab, text="0.0")
            imeas.grid(row=i+1, column=4)
            status = tk.Canvas(self.lv_tab, width=20, height=20)
            status.grid(row=i+1, column=5)
            apply_btn = ttk.Button(self.lv_tab, text="Apply", command=lambda ch=i+1, ve=vset, ie=iset: self.queue_vi_set(self.lv_wiener, ch, ve, ie))
            apply_btn.grid(row=i+1, column=6)
            for e in (vset, iset):
                e.bind("<FocusIn>", self.pause_refresh)
                e.bind("<FocusOut>", self.resume_refresh)
                e.bind("<Return>", lambda event, ch=i+1, ve=vset, ie=iset: self.queue_vi_set(self.lv_wiener, ch, ve, ie))
            row.extend([vset, vmeas, iset, imeas, status])
            self.lv_entries.append(row)

    def pause_refresh(self, event=None):
        self.refresh_paused = True

    def resume_refresh(self, event=None):
        self.refresh_paused = False

    def queue_voltage_set(self, device, channel, entry):
        try:
            value = float(entry.get())
            self.command_queue.put(lambda: device.set_voltage(channel, value))
        except ValueError:
            pass

    def queue_vi_set(self, device, channel, ventry, ientry):
        try:
            vval = float(ventry.get())
            ival = float(ientry.get())
            self.command_queue.put(lambda: device.set_output(channel, vval, ival))
        except ValueError:
            pass

    def queue_crate_power(self, state: bool):
        self.command_queue.put(lambda: self.hv_wiener.set_crate_power(state))
        self.command_queue.put(lambda: self.lv_wiener.set_crate_power(state))

    def all_off(self):
        self.command_queue.put(lambda: self.hv_wiener.all_off())
        self.command_queue.put(lambda: self.lv_wiener.all_off())

    def clear_all_events(self):
        self.command_queue.put(lambda: self.hv_wiener.clear_all_events())
        self.command_queue.put(lambda: self.lv_wiener.clear_all_events())

    def start_refresh_loop(self):
        def loop():
            while True:
                if not self.refresh_paused:
                    # Process all queued commands first (blocking)
                    while not self.command_queue.empty():
                        cmd = self.command_queue.get()
                        try:
                            cmd()
                        except Exception as e:
                            print(f"Command failed: {e}")
                        self.command_queue.task_done()

                    current_tab = self.notebook.tab(self.notebook.select(), "text")
                    if current_tab == "HV Channels":
                        for i, row in enumerate(self.hv_entries, start=1):
                            self.executor.submit(self.update_hv_row, i, row)
                    else:
                        for i, row in enumerate(self.lv_entries, start=1):
                            self.executor.submit(self.update_lv_row, i, row)
                time.sleep(2)

        threading.Thread(target=loop, daemon=True).start()

    def update_hv_row(self, ch, row):
        try:
            vmeas = self.hv_wiener.meas_term_voltage(ch)
            status_flags = self.hv_wiener.get_output_status(ch)
            self.root.after(0, lambda: row[1].config(text=f"{vmeas:.2f}"))
            color = "green" if "outputConstantVoltage" in status_flags else "red"
            self.root.after(0, lambda: row[2].create_rectangle(0, 0, 20, 20, fill=color))
        except Exception as e:
            print(f"HV update error {ch}: {e}")

    def update_lv_row(self, ch, row):
        try:
            vmeas = self.lv_wiener.meas_term_voltage(ch)
            imeas = self.lv_wiener.meas_current(ch)
            status_flags = self.lv_wiener.get_output_status(ch)
            self.root.after(0, lambda: row[1].config(text=f"{vmeas:.2f}"))
            self.root.after(0, lambda: row[3].config(text=f"{imeas:.2f}"))
            color = "green" if "outputConstantVoltage" in status_flags else "red"
            self.root.after(0, lambda: row[4].create_rectangle(0, 0, 20, 20, fill=color))
        except Exception as e:
            print(f"LV update error {ch}: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = WienerGUI(root)
    root.mainloop()
