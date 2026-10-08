#!/usr/bin/env python3
"""Langrisser III English patch: build launcher.

A small window around build.py for people who would rather not use a
terminal: pick the Japanese disc folder, choose whether to build the English
opening movie, press Build, then open the folder with the patched game.

Run:  python3 launcher.py   (Windows: double-click, or `py launcher.py`)
"""
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT / "tools"))

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText
except ImportError:
    print("The launcher needs Tkinter, which this Python does not include.\n"
          "  Debian/Ubuntu: sudo apt install python3-tk\n"
          "  Fedora:        sudo dnf install python3-tkinter\n"
          "Or build from the terminal: python3 build.py --jp-iso <disc folder>")
    sys.exit(1)

import launcher_core as lc  # noqa: E402

VERSION = (PROJECT / "VERSION").read_text(encoding="utf-8").strip()


class Launcher(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(f"Langrisser III English Patch v{VERSION}")
        self.minsize(640, 460)
        self.settings = lc.load_settings()
        self.proc = None
        self.lines = queue.Queue()
        self.log_lines = []
        self.result = None

        start_dir = self.settings.get("disc_dir") or os.environ.get("LANG3_JP_DIR", "")
        self.disc_var = tk.StringVar(value=start_dir)
        self.movie_var = tk.BooleanVar(value=bool(self.settings.get("encode_movie")))
        self.has_ffmpeg = shutil.which("ffmpeg") is not None
        if not self.has_ffmpeg:
            self.movie_var.set(False)

        self._layout()
        self.disc_var.trace_add("write", lambda *_: self._check_disc())
        self._check_disc()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # --- layout ------------------------------------------------------------

    def _layout(self):
        pad = {"padx": 10, "pady": 4}
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=6, pady=6)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Japanese disc folder (.cue + Track .bin files)").grid(
            row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.disc_var).grid(
            row=1, column=0, sticky="ew", **pad)
        ttk.Button(frame, text="Browse…", command=self._browse).grid(
            row=1, column=1, **pad)
        self.disc_status = ttk.Label(frame, text="")
        self.disc_status.grid(row=2, column=0, columnspan=2, sticky="w", **pad)

        movie_text = "Build the English opening movie (needs ffmpeg, takes longer)"
        if not self.has_ffmpeg:
            movie_text += ": ffmpeg not found"
        self.movie_box = ttk.Checkbutton(frame, text=movie_text, variable=self.movie_var)
        self.movie_box.grid(row=3, column=0, columnspan=2, sticky="w", **pad)
        if not self.has_ffmpeg:
            self.movie_box.state(["disabled"])

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="ew", **pad)
        self.build_btn = ttk.Button(buttons, text="Build patched game", command=self._build)
        self.build_btn.pack(side="left")
        self.open_btn = ttk.Button(buttons, text="Open output folder",
                                   command=self._open_output, state="disabled")
        self.open_btn.pack(side="left", padx=8)
        self.progress = ttk.Progressbar(buttons, mode="indeterminate", length=160)
        self.progress.pack(side="right")

        self.log = ScrolledText(frame, height=16, state="disabled", wrap="word")
        self.log.grid(row=5, column=0, columnspan=2, sticky="nsew", **pad)
        frame.rowconfigure(5, weight=1)

    # --- disc folder -------------------------------------------------------

    def _browse(self):
        start = self.disc_var.get() or str(Path.home())
        chosen = filedialog.askdirectory(initialdir=start,
                                         title="Choose the Japanese disc folder")
        if chosen:
            self.disc_var.set(chosen)

    def _check_disc(self):
        path = self.disc_var.get().strip()
        if not path:
            ok, msg = False, "Choose the folder that holds your Japanese disc image."
        else:
            ok, msg = lc.check_disc_dir(Path(path))
        self.disc_status.config(text=("✓ " if ok else "✗ ") + msg,
                                foreground="#1a7f37" if ok else "#b42318")
        if self.proc is None:
            self.build_btn.state(["!disabled"] if ok else ["disabled"])
        return ok

    # --- build -------------------------------------------------------------

    def _build(self):
        if not self._check_disc():
            return
        disc = Path(self.disc_var.get().strip())
        self.settings.update(disc_dir=str(disc), encode_movie=self.movie_var.get())
        try:
            lc.save_settings(self.settings)
        except OSError:
            pass  # remembering the folder is a convenience, never a blocker

        self.log_lines = []
        self.result = None
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")
        self.build_btn.state(["disabled"])
        self.open_btn.state(["disabled"])
        self.progress.start(12)

        cmd = lc.build_command(disc, self.movie_var.get())
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.proc = subprocess.Popen(
            cmd, cwd=PROJECT, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", creationflags=flags)
        threading.Thread(target=self._read_output, daemon=True).start()
        self.after(100, self._poll)

    def _read_output(self):
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def _poll(self):
        done = False
        try:
            while True:
                line = self.lines.get_nowait()
                if line is None:
                    done = True
                    break
                self.log_lines.append(line)
                self.log.config(state="normal")
                self.log.insert("end", line)
                self.log.see("end")
                self.log.config(state="disabled")
        except queue.Empty:
            pass
        if done:
            self._finish()
        else:
            self.after(100, self._poll)

    def _finish(self):
        code = self.proc.wait()
        self.proc = None
        self.progress.stop()
        self._check_disc()
        self.result = lc.output_folder(self.log_lines)
        if code == 0 and self.result is not None:
            self.open_btn.state(["!disabled"])
            messagebox.showinfo("Build complete",
                                f"The patched game is in:\n{self.result}\n\n"
                                "Load the .cue file in your emulator.")
        else:
            messagebox.showerror("Build failed",
                                 "The build stopped. The log shows why.")

    def _open_output(self):
        if self.result is not None:
            subprocess.Popen(lc.open_folder_command(self.result))

    def _on_close(self):
        if self.proc is not None:
            if not messagebox.askyesno("Build running",
                                       "A build is still running. Stop it and quit?"):
                return
            self.proc.terminate()
        self.destroy()


if __name__ == "__main__":
    Launcher().mainloop()
