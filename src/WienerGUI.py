"""
Tkinter GUI for controlling a WIENER EHS (HV) + MPOD (LV) crate.
- 8 HV channels: voltage set + measured, enable/disable, status, indicator.
- 8 LV channels: voltage & current set + measured, enable/disable, status, indicator.
- Periodic refresh (configurable) of setpoints & measurements.
- Non-blocking SNMP calls using a thread pool so the UI stays responsive.

Prereqs:
- pysnmp (async v3arch present, but Wiener wrapper below already uses asyncio.run)
- utils.py providing FloatOpaque, opaque_to_float, switch_to_int, LoggingFormat
- The `Wiener` class supplied by the user (imported here).

Usage:
  python wiener_gui.py

Edit HOST/MIB_DIR/MIB_NAME if needed.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from functools import partial
import concurrent.futures
import queue
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Tuple

from pathlib import Path
import sys
path_root = Path(__file__).parents[2]
sys.path.append(str(path_root))

from Wiener import Wiener

# ---------------- Configuration ----------------
HOST = "10.179.59.29"           # crate IP
MIB_DIR = "/usr/share/snmp/mibs"
MIB_NAME = "WIENER-CRATE-MIB"
POLL_MS = 2000                  # periodic refresh interval (milliseconds)
MAX_WORKERS = 6                 # threadpool for SNMP calls

HV_CHANNELS = list(range(1, 9))
LV_CHANNELS = list(range(1, 9))

# -------------- Helper widgets/styles --------------
class Led(ttk.Frame):
    """A small colored square used as an ON/OFF indicator."""
    def __init__(self, master, size: int = 16):
        super().__init__(master)
        self._cv = tk.Canvas(self, width=size, height=size, highlightthickness=0)
        self._cv.pack()
        self._rect = self._cv.create_rectangle(0, 0, size, size, outline="", fill="#9e9e9e")

    def set_color(self, color: str):
        self._cv.itemconfigure(self._rect, fill=color)


# -------------- GUI App --------------
class WienerGUI(tk.Tk):
 
    def __init__(self, root):
        self.root = root
        self.root.title("Wiener Crate HV/LV Controller")

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
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Create Wiener device objects
        self.hv_wiener = Wiener(HOST, MIB_DIR, MIB_NAME, 'HV')
        self.lv_wiener = Wiener(HOST, MIB_DIR, MIB_NAME, 'LV')

        self.build_hv_tab()
        self.build_lv_tab()

        self.start_refresh_loop()

    def build_tab(self, frame, widget_dict, channels, hv=True):
        columns = ("Channel", "Set V", "Meas V") if hv else ("Channel", "Set V", "Meas V", "Meas I")
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        tree.pack(expand=True, fill="both")


        # Bind editing events
        tree.bind("<Double-1>", self.start_edit)
        tree.bind("<FocusOut>", self.end_edit)
        tree.bind("<Return>", self.end_edit)


        for ch in range(channels):
            if hv:
                tree.insert("", "end", iid=ch, values=(ch, "", ""))
            else:
                tree.insert("", "end", iid=ch, values=(ch, "", "", ""))
        widget_dict["tree"] = tree


    def start_edit(self, event):
        self.editing = True


    def end_edit(self, event):
        self.editing = False


    def refresh_visible(self):
        if not self.editing:
        # Determine which tab is visible
            current_tab = self.notebook.tab(self.notebook.select(), "text")
            if current_tab == "HV":
                self.executor.submit(self.refresh_tab, self.hv_widgets, hv=True)
            elif current_tab == "LV":
                self.executor.submit(self.refresh_tab, self.lv_widgets, hv=False)
        self.root.after(self.refresh_interval * 1000, self.refresh_visible)


    def refresh_tab(self, widget_dict, hv=True):
        tree = widget_dict["tree"]
        for ch in tree.get_children():
            if hv:
            # Replace with SNMP calls
                set_v = f"{float(ch)*10:.2f}"
                meas_v = f"{float(ch)*10+0.5:.2f}"
                tree.item(ch, values=(ch, set_v, meas_v))
            else:
                set_v = f"{float(ch)*5:.2f}"
                meas_v = f"{float(ch)*5+0.3:.2f}"
                meas_i = f"{float(ch)*0.1:.3f}"
                tree.item(ch, values=(ch, set_v, meas_v, meas_i))
    # ---------- Styles ----------
    def _build_styles(self):
        style = ttk.Style(self)
        # Choose a theme that supports styles
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TButton", padding=6)
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Small.TLabel", font=("Segoe UI", 9))
        style.configure("Mono.TLabel", font=("Consolas", 10))

    # ---------- Layout ----------
    def _build_layout(self):
        # Top control bar
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(top, text="Crate Main Power:", style="Header.TLabel").pack(side=tk.LEFT)
        self.crate_power_var = tk.BooleanVar(value=self._read_crate_power_safe())
        self.crate_power_btn = ttk.Checkbutton(top, text="ON/OFF", variable=self.crate_power_var,
                                               command=self._toggle_crate_power)
        self.crate_power_btn.pack(side=tk.LEFT, padx=10)

        ttk.Button(top, text="Clear ALL Events (HV)", command=partial(self._run_bg, self.hv.clear_all_events)).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Clear ALL Events (LV)", command=partial(self._run_bg, self.lv.clear_all_events)).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="All OFF (HV)", command=partial(self._run_bg, self.hv.all_off)).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="All OFF (LV)", command=partial(self._run_bg, self.lv.all_off)).pack(side=tk.LEFT, padx=4)

        ttk.Label(top, text="Refresh (ms):").pack(side=tk.LEFT, padx=(16, 4))
        self.poll_var = tk.IntVar(value=POLL_MS)
        poll_entry = ttk.Entry(top, textvariable=self.poll_var, width=8)
        poll_entry.pack(side=tk.LEFT)
        ttk.Button(top, text="Apply Interval", command=self._apply_poll_interval).pack(side=tk.LEFT, padx=6)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(top, textvariable=self.status_var, style="Mono.TLabel").pack(side=tk.RIGHT)

        # Notebook for HV/LV tabs
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.hv_tab = ttk.Frame(nb)
        self.lv_tab = ttk.Frame(nb)
        nb.add(self.hv_tab, text="HV (EHS)")
        nb.add(self.lv_tab, text="LV (MPOD)")

        self.hv_widgets = self._build_hv_table(self.hv_tab)
        self.lv_widgets = self._build_lv_table(self.lv_tab)

    def _build_hv_table(self, parent) -> Dict[int, dict]:
        hdr = ["Ch", "Enabled", "Set V [V]", "Meas V [V]", "Status", "Apply", "Clear Evts"]
        grid = ttk.Frame(parent)
        grid.pack(fill=tk.BOTH, expand=True)

        for c, text in enumerate(hdr):
            ttk.Label(grid, text=text, style="Header.TLabel").grid(row=0, column=c, padx=6, pady=6)

        widgets: Dict[int, dict] = {}
        for i, ch in enumerate(HV_CHANNELS, start=1):
            row = i
            led = Led(grid)
            led.grid(row=row, column=1, padx=6)

            enabled_var = tk.BooleanVar(value=False)
            toggle_btn = ttk.Checkbutton(grid, text=f"CH {ch}", variable=enabled_var,
                                         command=partial(self._toggle_output, self.hv, ch, enabled_var))
            toggle_btn.grid(row=row, column=0, padx=6, sticky="w")

            v_set = tk.StringVar()
            v_meas = tk.StringVar()
            e_vset = ttk.Entry(grid, textvariable=v_set, width=10)
            e_vset.grid(row=row, column=2, padx=6)
            l_vmeas = ttk.Label(grid, textvariable=v_meas)
            l_vmeas.grid(row=row, column=3, padx=6)

            status_var = tk.StringVar()
            ttk.Label(grid, textvariable=status_var, style="Small.TLabel", wraplength=360, justify=tk.LEFT).grid(row=row, column=4, padx=6, sticky="w")

            ttk.Button(grid, text="Apply V", command=partial(self._apply_hv, ch, v_set)).grid(row=row, column=5, padx=6)
            ttk.Button(grid, text="Clear", command=partial(self._run_bg, self.hv.clear_events, ch)).grid(row=row, column=6, padx=6)

            widgets[ch] = {
                "led": led,
                "enabled_var": enabled_var,
                "v_set": v_set,
                "v_meas": v_meas,
                "status": status_var,
            }
        return widgets

    def _build_lv_table(self, parent) -> Dict[int, dict]:
        hdr = ["Ch", "Enabled", "Set V [V]", "Meas V [V]", "Set I [A]", "Meas I [A]", "Status", "Apply", "Clear Evts"]
        grid = ttk.Frame(parent)
        grid.pack(fill=tk.BOTH, expand=True)

        for c, text in enumerate(hdr):
            ttk.Label(grid, text=text, style="Header.TLabel").grid(row=0, column=c, padx=6, pady=6)

        widgets: Dict[int, dict] = {}
        for i, ch in enumerate(LV_CHANNELS, start=1):
            row = i
            led = Led(grid)
            led.grid(row=row, column=1, padx=6)

            enabled_var = tk.BooleanVar(value=False)
            toggle_btn = ttk.Checkbutton(grid, text=f"CH {ch}", variable=enabled_var,
                                         command=partial(self._toggle_output, self.lv, ch, enabled_var))
            toggle_btn.grid(row=row, column=0, padx=6, sticky="w")

            v_set = tk.StringVar()
            v_meas = tk.StringVar()
            i_set = tk.StringVar()
            i_meas = tk.StringVar()

            ttk.Entry(grid, textvariable=v_set, width=10).grid(row=row, column=2, padx=6)
            ttk.Label(grid, textvariable=v_meas).grid(row=row, column=3, padx=6)

            ttk.Entry(grid, textvariable=i_set, width=10).grid(row=row, column=4, padx=6)
            ttk.Label(grid, textvariable=i_meas).grid(row=row, column=5, padx=6)

            status_var = tk.StringVar()
            ttk.Label(grid, textvariable=status_var, style="Small.TLabel", wraplength=320, justify=tk.LEFT).grid(row=row, column=6, padx=6, sticky="w")

            ttk.Button(grid, text="Apply V/I", command=partial(self._apply_lv, ch, v_set, i_set)).grid(row=row, column=7, padx=6)
            ttk.Button(grid, text="Clear", command=partial(self._run_bg, self.lv.clear_events, ch)).grid(row=row, column=8, padx=6)

            widgets[ch] = {
                "led": led,
                "enabled_var": enabled_var,
                "v_set": v_set,
                "v_meas": v_meas,
                "i_set": i_set,
                "i_meas": i_meas,
                "status": status_var,
            }
        return widgets

    # ---------- Polling ----------
    def _schedule_poll(self):
        if not self._polling:
            return
        self._refresh_all()
        self.after(self.poll_var.get(), self._schedule_poll)

    def _apply_poll_interval(self):
        try:
            val = int(self.poll_var.get())
            if val < 250:
                raise ValueError
            self.status_var.set(f"Refresh set to {val} ms")
        except Exception:
            messagebox.showerror("Invalid Interval", "Please enter an integer >= 250 ms")

    def _refresh_all(self):
        for ch in HV_CHANNELS:
            self._run_bg(self._refresh_hv_channel, ch)
        for ch in LV_CHANNELS:
            self._run_bg(self._refresh_lv_channel, ch)
        self._run_bg(self._refresh_crate_power)

    # ---------- Background task helpers ----------
    def _run_bg(self, func, *args, **kwargs):
        """Run a callable in the threadpool and attach completion handling."""
        future = self.executor.submit(self._safe_call, func, *args, **kwargs)
        with self._futures_lock:
            self._futures.add(future)
        future.add_done_callback(self._on_future_done)
        return future

    def _safe_call(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return e

    def _on_future_done(self, fut: concurrent.futures.Future):
        with self._futures_lock:
            self._futures.discard(fut)
        res = fut.result()
        if isinstance(res, Exception):
            # Show error in status bar (don't spam modal dialogs during polling)
            self.after(0, lambda: self.status_var.set(f"Error: {res}"))

    # ---------- Crate Power ----------
    def _refresh_crate_power(self):
        state = self._read_crate_power_safe()
        self.after(0, lambda: self.crate_power_var.set(state))

    def _read_crate_power_safe(self) -> bool:
        try:
            return self.hv.get_crate_power()
        except Exception:
            return False

    def _toggle_crate_power(self):
        desired = self.crate_power_var.get()
        self._run_bg(self.hv.set_crate_power, desired)
        self.status_var.set(f"Crate power -> {'ON' if desired else 'OFF'}")

    # ---------- Apply actions ----------
    def _toggle_output(self, dev: Wiener, ch: int, var: tk.BooleanVar):
        desired = var.get()
        self.status_var.set(f"CH{ch} {'ON' if desired else 'OFF'} (request)")
        self._run_bg(dev.enable_output, ch, 1 if desired else 0)

    def _apply_hv(self, ch: int, v_set_var: tk.StringVar):
        try:
            v = float(v_set_var.get())
        except Exception:
            messagebox.showerror("Invalid Voltage", f"HV CH{ch}: enter a numeric voltage")
            return
        self.status_var.set(f"HV CH{ch} set V -> {v}")
        self._run_bg(self.hv.set_voltage, ch, v)

    def _apply_lv(self, ch: int, v_set_var: tk.StringVar, i_set_var: tk.StringVar):
        v = None
        i = None
        try:
            v = float(v_set_var.get())
        except Exception:
            pass
        try:
            i = float(i_set_var.get())
        except Exception:
            pass

        if v is None and i is None:
            messagebox.showerror("Invalid Setpoints", f"LV CH{ch}: enter voltage and/or current")
            return

        if v is not None:
            self._run_bg(self.lv.set_voltage, ch, v)
        if i is not None:
            self._run_bg(self.lv.set_current, i, ch)
        self.status_var.set(f"LV CH{ch} apply V={v if v is not None else '-'} I={i if i is not None else '-'}")

    # ---------- Refresh per-channel ----------
    def _refresh_hv_channel(self, ch: int):
        try:
            enabled = self.hv.output_enabled(ch)
            v_set = self.hv.get_voltage(ch)              # setpoint
            v_meas = self.hv.meas_term_voltage(ch)       # measured terminal voltage
            status_list = self.hv.get_output_status(ch)  # list of active flags
        except Exception as e:
            # Push error to UI
            self.after(0, lambda: self.status_var.set(f"HV CH{ch} error: {e}"))
            return

        def apply():
            w = self.hv_widgets[ch]
            w["enabled_var"].set(bool(enabled))
            w["v_set"].set(f"{v_set:.3f}")
            w["v_meas"].set(f"{v_meas:.3f}")
            # LED color: green if enabled & constant voltage, amber if enabled but not CV, red otherwise
            status_txt = ", ".join(status_list) if status_list else "ok"
            if enabled:
                color = "#4caf50" if "outputConstantVoltage" in status_list else "#ffc107"
            else:
                color = "#e53935"
            w["led"].set_color(color)
            w["status"].set(status_txt)
        self.after(0, apply)

    def _refresh_lv_channel(self, ch: int):
        try:
            enabled = self.lv.output_enabled(ch)
            v_set = self.lv.get_voltage(ch)
            v_meas = self.lv.meas_term_voltage(ch)
            i_set = self.lv.get_current(ch)
            i_meas = self.lv.meas_current(ch)
            status_list = self.lv.get_output_status(ch)
        except Exception as e:
            self.after(0, lambda: self.status_var.set(f"LV CH{ch} error: {e}"))
            return

        def apply():
            w = self.lv_widgets[ch]
            w["enabled_var"].set(bool(enabled))
            w["v_set"].set(f"{v_set:.3f}")
            w["v_meas"].set(f"{v_meas:.3f}")
            w["i_set"].set(f"{i_set:.6f}")
            w["i_meas"].set(f"{i_meas:.6f}")
            status_txt = ", ".join(status_list) if status_list else "ok"
            if enabled:
                color = "#4caf50" if "outputConstantVoltage" in status_list else "#ffc107"
            else:
                color = "#e53935"
            w["led"].set_color(color)
            w["status"].set(status_txt)
        self.after(0, apply)

    # ---------- Cleanup ----------
    def _on_close(self):
        self._polling = False
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = WienerGUI(root)
    app.mainloop()
