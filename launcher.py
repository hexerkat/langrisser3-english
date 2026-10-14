#!/usr/bin/env python3
"""Langrisser III English patch: build launcher.

A small window around build.py for people who would rather not use a
terminal: pick the Japanese disc folder, choose whether to build the English
opening movie, press Build, then open the folder with the patched game.
Once a disc is picked, the background shows Tiaris, Diehärte or Altemüller
(picked at random) from that disc's own gallery (LANG/OMAKE/GRAPHIC.LZH);
nothing from the game ships with the patcher.

Run:  python3 launcher.py   (Windows: double-click, or `py launcher.py`)
With arguments it is the command-line build: launcher.py --jp-iso <folder>.
Packaged as a standalone executable by launcher.spec (PyInstaller).
"""
import contextlib
import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "tools"))

if len(sys.argv) > 1:
    # Any argument: behave exactly like build.py on the command line.
    if sys.stdout is None:   # windowed Windows executable: no console
        sys.stdout = sys.stderr = open(Path(sys.executable).with_name("build.log"),
                                       "w", encoding="utf-8")
    import build
    raise SystemExit(build.main(sys.argv[1:]))

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

import host_env  # noqa: E402
import launcher_core as lc  # noqa: E402

VERSION = (PROJECT / "VERSION").read_text(encoding="utf-8").strip()


class _QueueWriter:
    """File-like sink that hands each written chunk to the window."""

    def __init__(self, q):
        self.q = q

    def write(self, text):
        if text:
            self.q.put(text)
        return len(text)

    def flush(self):
        pass


class Launcher(tk.Tk):

    W, H = lc.WINDOW_SIZE            # the gallery picture at 2/3
    TOP = 300                        # the picture is clear above this row
    PANEL = (0, TOP, W, H)           # the controls, lower part, full width
    PAD = 24
    LOG_LINES = 2
    BG = "#1b2130"
    TEXT, DIM = "#ffffff", "#c9d1e0"
    OK, BAD = "#7ee08a", "#ff8a80"
    ACCENT, ACCENT_HOVER = "#c8562a", "#e0703a"

    def __init__(self):
        super().__init__()
        self.title(f"Langrisser III English Patch v{VERSION}")
        self.resizable(False, False)
        self.settings = lc.load_settings()
        self.running = False
        self.lines = queue.Queue()
        self.log_lines = []
        self.result = None
        self.checks = {}            # disc folder -> lc.DiscCheck
        self.pictures = {}          # disc folder -> PPM bytes of its background
        self.verifying = set()      # folders being verified right now
        self.photo = None

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

    def _text(self, x, y, text="", fill=None, tag=None, **kw):
        return self.canvas.create_text(x, y, text=text, fill=fill or self.TEXT,
                                       anchor="nw", tags=tag, **kw)

    def _set_text(self, tag, text, fill=None):
        self.canvas.itemconfigure(tag, text=text, **({"fill": fill} if fill else {}))

    def _style(self):
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        edge, face, hover, field = "#4a5670", "#2b3446", "#3b4760", "#10141d"
        style.configure("TButton", background=face, foreground=self.TEXT, bordercolor=edge,
                        lightcolor=face, darkcolor=face, focuscolor=face, padding=(12, 6))
        style.map("TButton", background=[("disabled", "#20273a"), ("active", hover)],
                  foreground=[("disabled", "#76809a")])
        style.configure("Build.TButton", background=self.ACCENT, bordercolor=self.ACCENT,
                        lightcolor=self.ACCENT, darkcolor=self.ACCENT, focuscolor=self.ACCENT,
                        padding=(22, 10), font=("TkDefaultFont", 11, "bold"))
        style.map("Build.TButton",
                  background=[("disabled", "#3a2a24"), ("active", self.ACCENT_HOVER)],
                  foreground=[("disabled", "#8a7a74")])
        style.configure("TEntry", fieldbackground=field, foreground=self.TEXT,
                        insertcolor=self.TEXT, bordercolor=edge, lightcolor=field,
                        darkcolor=field, padding=(6, 5))
        style.configure("Horizontal.TProgressbar", troughcolor=field, background=self.ACCENT_HOVER,
                        bordercolor=edge, lightcolor=self.ACCENT_HOVER, darkcolor=self.ACCENT_HOVER)

    def _layout(self):
        self._style()
        W, H, P, top = self.W, self.H, self.PAD, self.TOP
        c = self.canvas = tk.Canvas(self, width=W, height=H, highlightthickness=0, bg=self.BG)
        c.pack()
        self.bg_item = c.create_image(0, 0, anchor="nw")

        # Title, top left, with a soft shadow so it reads over the sky.
        for dx, color in ((2, "#000000"), (0, self.TEXT)):
            self._text(P + dx, 18 + dx, "Langrisser III", fill=color,
                       font=("TkDefaultFont", 24, "bold"))
            self._text(P + 2 + dx, 60 + dx, f"English Patch  v{VERSION}", fill=color,
                       font=("TkDefaultFont", 12))

        # Disc folder: label, a wide field and Browse on one row, status below.
        self._text(P, top + 18, "Japanese disc folder (.cue + Track .bin files)", fill=self.DIM)
        browse = ttk.Button(c, text="Browse…", command=self._browse)
        c.create_window(W - P, top + 42, window=browse, anchor="ne")
        entry = ttk.Entry(c, textvariable=self.disc_var)
        c.create_window(P, top + 42, window=entry, anchor="nw", width=W - 2 * P - 120,
                        height=34)
        self._text(P, top + 86, tag="status", width=W - 2 * P)

        # Movie option drawn on the canvas: a ttk checkbox is an opaque box.
        on = self.has_ffmpeg
        color = self.TEXT if on else "#76809a"
        y = top + 122
        c.create_rectangle(P + 1, y + 3, P + 17, y + 19, outline=color, width=1, tags="movie")
        self._text(P + 3, y, "", fill=self.OK, tag="movie_mark",
                   font=("TkDefaultFont", 11, "bold"))
        label = ("Also build the English opening movie (needs ffmpeg, takes longer)" if on
                 else "English opening movie: ffmpeg not found, the opening stays Japanese")
        self._text(P + 28, y + 2, label, tag="movie", fill=self.DIM if on else color)
        if on:
            for t in ("movie", "movie_mark"):
                c.tag_bind(t, "<Button-1>", lambda e: self.movie_var.set(not self.movie_var.get()))
                c.tag_bind(t, "<Enter>", lambda e: c.config(cursor="hand2"))
                c.tag_bind(t, "<Leave>", lambda e: c.config(cursor=""))
        self.movie_var.trace_add("write", lambda *_: self._draw_movie())
        self._draw_movie()

        # Build, with the progress bar beside it.
        self.build_btn = ttk.Button(c, text="Build patched game", command=self._build,
                                    style="Build.TButton")
        c.create_window(P, top + 166, window=self.build_btn, anchor="nw")
        self.progress = ttk.Progressbar(c, mode="indeterminate")
        self.progress_item = c.create_window(P + 230, top + 180, window=self.progress,
                                             anchor="nw", width=W - 2 * P - 230,
                                             state="hidden")

        # Last log lines, and the folder / log buttons, along the bottom.
        self._text(P, H - 50, tag="log", fill=self.DIM, font=("TkFixedFont", 9),
                   width=W - 2 * P - 260)
        self.log_btn = ttk.Button(c, text="View log", command=self._show_log)
        c.create_window(W - P, H - P, window=self.log_btn, anchor="se")
        self.open_btn = ttk.Button(c, text="Open folder",
                                   command=self._open_output, state="disabled")
        c.create_window(W - P - 132, H - P, window=self.open_btn, anchor="se")
        self.log_win = None

    def _draw_movie(self):
        self._set_text("movie_mark", "✓" if self.movie_var.get() else "")

    # --- disc verification + wallpaper ---------------------------------------

    def _busy(self, on):
        self.canvas.itemconfigure(self.progress_item, state="normal" if on else "hidden")
        (self.progress.start if on else self.progress.stop)(*((12,) if on else ()))

    def _verify(self, disc):
        """Check the disc content off the main thread; the verified picture
        becomes the background."""
        self.verifying.add(disc)
        self._busy(True)

        def work():
            check = lc.verify_disc(disc)
            data = None
            if check.ok:
                try:
                    w, h, rgb = lc.wallpaper(check.jpeg)
                    rgb = lc.shade(rgb, w, h, self.PANEL, 0.38)
                    data = lc.ppm(w, h, rgb)
                except Exception:  # noqa: BLE001 - verified disc, just no picture
                    data = None
            self.after(0, lambda: self._verified(disc, check, data))

        threading.Thread(target=work, daemon=True).start()

    def _verified(self, disc, check, data):
        self.verifying.discard(disc)
        self.checks[disc] = check
        if data is not None:
            self.pictures[disc] = data
        if not self.running and not self.verifying:
            self._busy(False)
        self._check_disc()

    def _show_picture(self, disc):
        data = self.pictures.get(disc)
        if data is None:
            self.photo = None
            self.canvas.itemconfigure(self.bg_item, image="")
            return
        self.photo = tk.PhotoImage(data=data, format="PPM")
        self.canvas.itemconfigure(self.bg_item, image=self.photo)

    # --- disc folder -------------------------------------------------------

    def _browse(self):
        start = self.disc_var.get() or str(Path.home())
        chosen = filedialog.askdirectory(initialdir=start,
                                         title="Choose the Japanese disc folder")
        if chosen:
            self.disc_var.set(chosen)

    def _check_disc(self):
        """Show the state of the chosen folder; True only once its content
        is verified. Names are checked at once, content in the background."""
        path = self.disc_var.get().strip()
        disc = Path(path) if path else None
        ok = False
        if disc is None:
            self._set_text("status", "✗ Choose the folder that holds your Japanese disc image.",
                           self.BAD)
        elif disc in self.checks:
            check = self.checks[disc]
            ok = check.ok
            self._set_text("status", ("✓ " if ok else "✗ ") + check.message,
                           self.OK if ok else self.BAD)
        else:
            names_ok, msg = lc.check_disc_dir(disc)
            if not names_ok:
                self._set_text("status", "✗ " + msg, self.BAD)
            else:
                self._set_text("status", lc.VERIFYING, self.DIM)
                if disc not in self.verifying:
                    self._verify(disc)
        self._show_picture(disc if ok else None)
        if not self.running:
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
        self._refresh_log()
        self.build_btn.state(["disabled"])
        self.open_btn.state(["disabled"])
        self._busy(True)

        self.running = True
        args = lc.build_args(disc, self.movie_var.get())
        threading.Thread(target=self._run_build, args=(args,), daemon=True).start()
        self.after(100, self._poll)

    def _run_build(self, args):
        """Run build.main in this process; its prints stream into the log."""
        out = _QueueWriter(self.lines)
        code = 1
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                import build
                code = build.main(args) or 0
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
            except Exception:  # noqa: BLE001 - show it in the log, keep the window
                traceback.print_exc()
        self.code = code
        self.lines.put(None)

    def _poll(self):
        done = False
        got = False
        try:
            while True:
                line = self.lines.get_nowait()
                if line is None:
                    done = True
                    break
                self.log_lines.append(line)
                got = True
        except queue.Empty:
            pass
        if got:
            self._refresh_log()
        if done:
            self._finish()
        else:
            self.after(100, self._poll)

    def _refresh_log(self):
        text = "".join(self.log_lines)
        tail = [ln.rstrip() for ln in text.splitlines() if ln.strip()][-self.LOG_LINES:]
        self._set_text("log", "\n".join(ln[:60] for ln in tail))
        if self.log_win is not None and self.log_win.winfo_exists():
            box = self.log_win.box
            box.config(state="normal")
            box.delete("1.0", "end")
            box.insert("end", text)
            box.see("end")
            box.config(state="disabled")

    def _show_log(self):
        if self.log_win is not None and self.log_win.winfo_exists():
            self.log_win.lift()
            return
        self.log_win = tk.Toplevel(self)
        self.log_win.title("Build log")
        self.log_win.box = ScrolledText(self.log_win, width=100, height=30,
                                        state="disabled", wrap="word")
        self.log_win.box.pack(fill="both", expand=True)
        self._refresh_log()

    def _finish(self):
        code = self.code
        self.running = False
        if not self.verifying:
            self._busy(False)
        self._check_disc()
        self.result = lc.output_folder("".join(self.log_lines).splitlines())
        if code == 0 and self.result is not None:
            self.open_btn.state(["!disabled"])
            messagebox.showinfo("Build complete",
                                f"The patched game is in:\n{self.result}\n\n"
                                "Load the .cue file in your emulator.")
        else:
            messagebox.showerror("Build failed",
                                 "The build stopped. View log shows why.")

    def _open_output(self):
        if self.result is not None:
            subprocess.Popen(lc.open_folder_command(self.result), env=host_env.external_env())

    def _on_close(self):
        if self.running:
            if not messagebox.askyesno("Build running",
                                       "A build is still running. Stop it and quit?"):
                return
            os._exit(1)
        self.destroy()


if __name__ == "__main__":
    Launcher().mainloop()
