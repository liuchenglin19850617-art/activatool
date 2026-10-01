import os
import sys
import ctypes
import tempfile
import subprocess
import customtkinter as ctk


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        f'"{os.path.abspath(sys.argv[0])}"', None, 1
    )
    sys.exit(0)


def check_activated():
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "(Get-CimInstance SoftwareLicensingProduct "
                "-Filter \"Name like 'Windows%' AND PartialProductKey is not null\")"
                ".LicenseStatus"
            ],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=15,
        )
        for line in result.stdout.splitlines():
            if line.strip() == "1":
                return True
    except Exception:
        pass
    return False


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("Activation Tool")
app.geometry("520x430")
app.resizable(False, False)
app.configure(fg_color="#0B1020")


if check_activated():
    app.title("本主机已激活")
    done_label = ctk.CTkLabel(
        app, text="本主机已激活", text_color="#4ADE80",
        font=ctk.CTkFont(size=22, weight="bold"),
    )
    done_label.place(relx=0.5, rely=0.5, anchor="center")
    app.mainloop()
    sys.exit(0)


spinner = ctk.CTkCanvas(app, width=64, height=64, bg="#0B1020", highlightthickness=0)
spinner.place(relx=0.5, rely=0.5, anchor="center")
spinner.create_oval(10, 10, 54, 54, outline="#25324A", width=5)
spinner_arc = spinner.create_arc(
    10, 10, 54, 54, start=0, extent=90,
    style="arc", outline="#3187FF", width=5,
)

progress_label = ctk.CTkLabel(
    app, text="0%", text_color="#FFFFFF",
    font=ctk.CTkFont(size=14),
)
progress_label.place(relx=0.5, rely=0.72, anchor="center")

msg_label = ctk.CTkLabel(
    app, text="", text_color="#FF6666",
    font=ctk.CTkFont(size=11), wraplength=480, justify="left",
)
msg_label.place(relx=0.5, rely=0.86, anchor="center")


commands = [
    ["cscript", "//nologo", r"C:\Windows\System32\slmgr.vbs", "/skms", "s1.kms.cx"],
    ["cscript", "//nologo", r"C:\Windows\System32\slmgr.vbs", "/ipk",
     "W269N-WFGWX-YVC9B-4J6C9-T83GX"],
    ["cscript", "//nologo", r"C:\Windows\System32\slmgr.vbs", "/ato"],
    ["cscript", "//nologo", r"C:\Windows\System32\slmgr.vbs", "/xpr"],
]

rotation = 0
progress = 0
command_index = 0
process = None
activation_failed = False
last_output = ""
finished = False


def rotate_spinner():
    global rotation, progress, command_index, process
    global activation_failed, last_output, finished

    if finished:
        return

    rotation = (rotation - 15) % 360
    spinner.itemconfigure(spinner_arc, start=rotation)

    if not activation_failed:
        if process is None and command_index < len(commands):
            outfile = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
            process = subprocess.Popen(
                commands[command_index],
                stdout=outfile, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            process._outfile = outfile

        elif process is not None and process.poll() is not None:
            process._outfile.close()
            try:
                with open(process._outfile.name, "r",
                          encoding="utf-8", errors="ignore") as f:
                    last_output = f.read().strip()
            except Exception:
                last_output = ""
            try:
                os.unlink(process._outfile.name)
            except Exception:
                pass

            if process.returncode != 0:
                activation_failed = True
            else:
                command_index += 1
            process = None

    if progress < 100:
        progress += 1
        progress_label.configure(text=f"{progress}%")

    all_done = activation_failed or (
        command_index >= len(commands) and process is None
    )

    if all_done and progress >= 100:
        finished = True
        if activation_failed:
            app.title("激活失败")
            progress_label.configure(text="激活失败", text_color="#FF5555")
            msg_label.configure(
                text=f"步骤 {command_index + 1} 失败:\n{last_output}"
            )
        else:
            app.title("已激活")
            progress_label.configure(text="激活成功", text_color="#4ADE80")
        return

    app.after(30, rotate_spinner)


rotate_spinner()
app.mainloop()