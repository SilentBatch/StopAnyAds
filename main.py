import os
import sys
import time
import threading
import shutil
import customtkinter as ctk
from tkinter import messagebox
import tkinter as tk

try:
    import psutil
except ImportError:
    psutil = None

APP_TITLE = "StopAnyAds"
ANYDESK_FOLDER_REL = os.path.join("AppData", "Roaming", "AnyDesk")
TARGET_DIR = os.path.join(os.path.expanduser("~"), ANYDESK_FOLDER_REL)
PROCESS_NAMES = {"AnyDesk.exe", "AnyDesk", "anydesk.exe", "anydesk"}

ctk.set_appearance_mode("system")  
ctk.set_default_color_theme("blue")

def get_colors():
    mode = ctk.get_appearance_mode()  
    if mode == "Dark":
        return {
            "bg": "#1e1e1e",
            "panel": "#2b2b2b",
            "accent": "#4f79ff",
            "accent_dark": "#3b5fd1",
            "text": "#ffffff",
            "muted": "#a1a1aa",
            "good": "#059669",
            "warn": "#d97706",
            "bad": "#dc2626",
            "textbox_bg": "#333333"
        }
    else:
        return {
            "bg": "#f5f7fb",
            "panel": "#ffffff",
            "accent": "#4f79ff",
            "accent_dark": "#3b5fd1",
            "text": "#1f2937",
            "muted": "#6b7280",
            "good": "#059669",
            "warn": "#d97706",
            "bad": "#dc2626",
            "textbox_bg": "#fafafa"
        }

def add_hover_animation(button, normal_color, hover_color, steps=10, delay=15):
    import colorsys

    def hex_to_rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def rgb_to_hex(rgb):
        return "#%02x%02x%02x" % tuple(int(c * 255) for c in rgb)

    def blend(c1, c2, t):
        return tuple(c1[i] * (1 - t) + c2[i] * t for i in range(3))

    normal_rgb = hex_to_rgb(normal_color)
    hover_rgb = hex_to_rgb(hover_color)
    current_step = 0
    direction = 0

    def update_color():
        nonlocal current_step, direction
        if direction == 0:
            return
        if direction == 1 and current_step < steps:
            current_step += 1
        elif direction == -1 and current_step > 0:
            current_step -= 1

        t = current_step / steps
        new_color = rgb_to_hex(blend(normal_rgb, hover_rgb, t))
        button.configure(fg_color=new_color)

        if (direction == 1 and current_step < steps) or (direction == -1 and current_step > 0):
            button.after(delay, update_color)

    def on_enter(e):
        nonlocal direction
        direction = 1
        update_color()

    def on_leave(e):
        nonlocal direction
        direction = -1
        update_color()

    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)

def terminate_anydesk_processes():
    killed = 0
    errors = 0
    used_taskkill = False

    if psutil is None:
        used_taskkill = True
        try:
            os.system('taskkill /IM AnyDesk.exe /F >nul 2>&1')
            os.system('taskkill /IM anydesk.exe /F >nul 2>&1')
        except Exception:
            errors += 1
    else:
        try:
            targets = []
            for proc in psutil.process_iter(attrs=["pid", "name"]):
                name = (proc.info.get("name") or "").strip()
                if name in PROCESS_NAMES or name.lower() in PROCESS_NAMES:
                    targets.append(proc)

            if targets:
                for proc in targets:
                    try:
                        proc.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        errors += 1
                gone, alive = psutil.wait_procs(targets, timeout=3)
                for proc in alive:
                    try:
                        proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        errors += 1
                killed = len(gone) + len(alive)
        except Exception:
            errors += 1

    return killed, errors, used_taskkill

def delete_anydesk_data(target_dir=TARGET_DIR):
    existed = os.path.isdir(target_dir)
    if not existed:
        return False, False, None
    try:
        def onerror(func, path, exc_info):
            try:
                os.chmod(path, 0o777)
                func(path)
            except Exception:
                pass
        shutil.rmtree(target_dir, onerror=onerror)
        return True, True, None
    except Exception as e:
        return False, True, str(e)

class StopAnyAdsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        icon_path = os.path.join(os.path.dirname(__file__), "logo.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        self.geometry("660x420")
        self.resizable(False, False)
        self.COLORS = get_colors()  

        self._build_ui()

    def _build_ui(self):
        colors = self.COLORS
        # Header
        header = ctk.CTkFrame(self, fg_color=colors["panel"], corner_radius=20)
        header.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header, text="StopAnyAds",
            font=("Segoe UI", 20, "bold"),
            text_color=colors["text"], fg_color="transparent"
        ).pack(anchor="w", padx=16, pady=(8, 0))

        ctk.CTkLabel(
            header,
            text="Removes annoying ads and resets AnyDesk ID. Work on a non-portable version not guaranteed.\n",
            font=("Segoe UI", 12), text_color=colors["muted"], fg_color="transparent"
        ).pack(anchor="w", padx=16)

        panel = ctk.CTkFrame(self, fg_color=colors["panel"], corner_radius=20)
        panel.pack(fill="both", expand=True, padx=20, pady=10)

        self.reset_btn = ctk.CTkButton(
            panel, text="Stop It!",
            fg_color=colors["accent"], text_color="white",
            font=("Segoe UI", 12, "bold"),
            corner_radius=12,
            command=self._confirm_reset
        )
        self.reset_btn.pack(anchor="w", padx=16, pady=(16, 10))
        add_hover_animation(self.reset_btn, colors["accent"], colors["accent_dark"])

        self.progress = ctk.CTkProgressBar(panel, width=580, corner_radius=10)
        self.progress.pack(padx=16, pady=8)
        self.progress.set(0)

        self.log = ctk.CTkTextbox(
            panel, corner_radius=10, fg_color=colors["textbox_bg"], text_color=colors["text"],
            font=("Consolas", 10), height=140
        )
        self.log.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self.log.insert("end", "The report will be displayed here...\n")
        self.log.configure(state="disabled")

        ctk.CTkLabel(
            self, text=f"Target folder: {TARGET_DIR}",
            font=("Segoe UI", 10), text_color=colors["muted"]
        ).pack(fill="x", padx=20, pady=(0, 12))

    def _confirm_reset(self):
        colors = self.COLORS
        popup = ctk.CTkToplevel(self)
        popup.title("Confirmation")
        popup.geometry("500x180")
        popup.resizable(False, False)
        icon_path = os.path.join(os.path.dirname(__file__), "logo.ico")
        def set_icon():
            if os.path.exists(icon_path):
                try:
                    popup.tk.call('wm', 'iconbitmap', popup._w, icon_path)
                except Exception:
                    pass

        set_icon()
        popup.after(300, set_icon) #yea i know, this is bad workaround
        ctk.CTkLabel(
                popup,
                text="Are you sure?\nThis will terminate AnyDesk and delete its data folder.",
                font=("Segoe UI", 14, "bold"),
                text_color=colors["text"]
            ).pack(pady=(16, 8))

        ctk.CTkLabel(
            popup,
            text="Operation cannot be undone. Close AnyDesk if it has unsaved work.",
            font=("Segoe UI", 11), text_color=colors["warn"]
        ).pack(pady=(0, 10))

        btns = ctk.CTkFrame(popup, fg_color="transparent")
        btns.pack(pady=(8, 12))

        yes_btn = ctk.CTkButton(
            btns, text="Yes", command=lambda: (popup.destroy(), self._start_reset()),
            fg_color=colors["accent"], text_color="white",
            corner_radius=8, width=100
        )
        yes_btn.grid(row=0, column=0, padx=8)
        add_hover_animation(yes_btn, colors["accent"], colors["accent_dark"])

        no_btn = ctk.CTkButton(
            btns, text="No", command=popup.destroy,
            fg_color=colors["panel"], text_color=colors["text"],
            corner_radius=8, width=100
        )
        no_btn.grid(row=0, column=1, padx=8)
        add_hover_animation(no_btn, colors["panel"], colors["muted"])

    def _start_reset(self):
        threading.Thread(target=self._reset_sequence, daemon=True).start()

    def _log(self, text, level="info"):
        prefix = {"info": "[*] ", "good": "[✓] ", "warn": "[!] ", "bad": "[x] "}.get(level, "[*] ")
        self.log.configure(state="normal")
        self.log.insert("end", f"{prefix}{text}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _reset_sequence(self):
        self.reset_btn.configure(state="disabled")
        self.progress.set(0)
        self._log("Starting reset...", "info")
        time.sleep(0.3)

        self._log("Terminating AnyDesk processes...", "info")
        killed, errors, used_taskkill = terminate_anydesk_processes()
        self.progress.set(0.3)
        if used_taskkill and psutil is None:
            self._log("Used system taskkill (psutil not installed).", "warn")
        self._log(f"Processes terminated: {killed}. Errors: {errors}.", "good")
        time.sleep(0.3)

        self._log(f"Deleting data folder: {TARGET_DIR}", "info")
        deleted, existed, err = delete_anydesk_data()
        self.progress.set(0.75)
        if err:
            self._log(f"Delete error: {err}", "bad")
        else:
            if existed and deleted:
                self._log("Data folder deleted successfully.", "good")
            elif not existed:
                self._log("Data folder not found. Possibly already removed.", "warn")
        time.sleep(0.3)

        self._log("Finalizing...", "info")
        time.sleep(0.3)
        self.progress.set(1)
        self._log("Done. AnyDesk stopped and data cleaned.", "good")
        self.reset_btn.configure(state="normal")


def show_disclaimer():
    root = ctk.CTk()
    root.withdraw()
    icon_path = os.path.join(os.path.dirname(__file__), "logo.ico")
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
    text = (
        "IMPORTANT DISCLAIMER\n\n"
        "This utility is provided ONLY for non-commercial use.\n"
        "By clicking “OK”, you acknowledge that you have read and agree.\n\n"
        "If you are a commercial user, please purchase an AnyDesk subscription."
    )
    res = messagebox.askokcancel("Non-commercial use only", text)
    root.destroy()
    return res


def main():
    if os.name != "nt":
        messagebox.showerror(APP_TITLE, f"{APP_TITLE} is intended for Windows.\nPlatform: {sys.platform}")
        sys.exit(0)

    if not show_disclaimer():
        sys.exit(0)

    app = StopAnyAdsApp()
    app.mainloop()


if __name__ == "__main__":
    main()
