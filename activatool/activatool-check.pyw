import queue
import random
import threading
import subprocess
import customtkinter as ctk


LICENSE_STATUS_MAP = {
    0: "未授权",
    1: "已激活",
    2: "初始宽限期",
    3: "宽限期已过",
    4: "非正版宽限期",
    5: "通知状态",
    6: "延长宽限期",
}

ERROR_CODE_MAP = {
    "0xC004F074": "无法联系任何密钥管理服务（KMS）服务器。请检查网络连接或 KMS 服务器地址是否可达。",
    "0xC004F069": "产品密钥与当前 Windows 版本不匹配。请确认密钥对应正确的系统版本。",
    "0xC004F050": "产品密钥无效。请检查密钥是否正确输入。",
    "0xC004F038": "KMS 服务器计数不足，无法激活。请联系 KMS 管理员增加激活计数。",
    "0xC004F039": "KMS 服务器未启用。请在 KMS 服务器上运行激活命令。",
    "0xC004F041": "KMS 服务器未激活。请先激活 KMS 主机。",
    "0xC004F042": "指定的 KMS 服务器无法使用。请更换可用的 KMS 地址。",
    "0xC004F035": "无法使用批量许可密钥激活此计算机。该密钥可能需要通过 KMS 或 MAK 方式激活。",
    "0xC004F051": "产品密钥已被阻止。该密钥可能已被微软封禁，请更换密钥。",
    "0xC004F06C": "KMS 请求时间戳无效。请检查系统时间和时区设置是否正确。",
    "0x80070005": "访问被拒绝。请以管理员身份运行本工具。",
    "0x8007007B": "DNS 名称不存在。KMS 客户端无法在 DNS 中找到 KMS 服务器记录。",
    "0x80070490": "产品密钥无效。请检查密钥后重试。",
    "0xC004C003": "激活服务器确定无法激活此计算机。请尝试更换密钥或联系管理员。",
    "0x8007232B": "DNS 名称不存在。无法通过 DNS 自动发现 KMS 服务器，请手动指定。",
    "0xC004C008": "产品密钥已被另一台计算机使用。请联系管理员或更换密钥。",
    "0x8004FE21": "此计算机未运行正版 Windows。系统可能被篡改或包含非正版组件。",
    "0xC004F00F": "硬件 ID 绑定超出容差范围。硬件变更过大导致激活失效，需重新激活。",
    "0xC004F014": "产品密钥不可用。请确认密钥已正确安装。",
    "0xC004F02C": "脱机激活数据格式不正确。请重新生成脱机激活请求。",
    "0xC004F064": "非正版宽限期已过期。请使用正版密钥重新激活。",
    "0xC004F065": "应用程序正在有效的非正版期间内运行。请尽快完成正版激活。",
}

CHANNEL_MAP = {
    "Retail": "零售版",
    "OEM:SLP": "OEM 系统锁定预安装",
    "OEM:NONSLP": "OEM 非 SLP",
    "OEM:DM": "OEM 数字标记",
    "Volume:GVLK": "批量许可 GVLK（KMS 客户端）",
    "Volume:MAK": "批量许可 MAK",
    "Volume:CSVLK": "批量许可 CSVLK（KMS 主机）",
    "Volume": "批量许可",
}


def run_ps(command):
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=20,
        )
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def parse_key_value(raw):
    data = {}
    for line in raw.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip()
    return data


def check_activation_status():
    ps = (
        "Get-CimInstance SoftwareLicensingProduct "
        "-Filter \"Name like 'Windows%' AND PartialProductKey is not null\" "
        "| Select-Object Name, Description, LicenseStatus, LicenseStatusReason, "
        "ProductKeyChannel, PartialProductKey, GracePeriodRemaining "
        "| Format-List"
    )
    return parse_key_value(run_ps(ps))


def get_kms_info():
    ps = (
        "Get-CimInstance SoftwareLicensingService "
        "| Select-Object KeyManagementServiceMachine, "
        "KeyManagementServicePort, DiscoveredKeyManagementServiceMachineName, "
        "DiscoveredKeyManagementServiceMachinePort "
        "| Format-List"
    )
    return parse_key_value(run_ps(ps))


def decode_error(code_str):
    try:
        code_int = int(code_str)
    except (ValueError, TypeError):
        return f"未知错误码：{code_str}"

    hex_code = f"0x{code_int:08X}"
    if hex_code in ERROR_CODE_MAP:
        return ERROR_CODE_MAP[hex_code]

    for key in ERROR_CODE_MAP:
        if key.lower() == hex_code.lower():
            return ERROR_CODE_MAP[key]

    return f"错误码：{hex_code}，该错误码暂未收录，请查阅微软官方文档。"


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("激活识别工具")
app.geometry("620x680")
app.resizable(False, False)
app.configure(fg_color="#0B1020")


state = {
    "percent": 0,
    "task_done": False,
    "splash_closed": False,
    "lic": {},
    "kms": {},
}

main_scroll = None


def add_section(parent, title, row):
    header = ctk.CTkLabel(
        parent, text=title, text_color="#3187FF",
        font=ctk.CTkFont(size=15, weight="bold"), anchor="w",
    )
    header.grid(row=row, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 4))
    return row + 1


def add_row(parent, label, value, row, value_color="#E0E0E0"):
    ctk.CTkLabel(
        parent, text=label, text_color="#8899AA",
        font=ctk.CTkFont(size=12), anchor="w",
    ).grid(row=row, column=0, sticky="w", padx=(30, 8), pady=2)

    val_label = ctk.CTkLabel(
        parent, text=value, text_color=value_color,
        font=ctk.CTkFont(size=12, weight="bold"),
        anchor="w", wraplength=380, justify="left",
    )
    val_label.grid(row=row, column=1, sticky="w", padx=(0, 20), pady=2)
    return row + 1


def build_main_ui():
    global main_scroll
    ctk.CTkLabel(
        app, text="激活识别工具", text_color="#FFFFFF",
        font=ctk.CTkFont(size=18, weight="bold"),
    ).pack(pady=(20, 8))

    main_scroll = ctk.CTkScrollableFrame(
        app, fg_color="#0B1020", scrollbar_button_color="#25324A",
        scrollbar_button_hover_color="#3187FF",
    )
    main_scroll.pack(fill="both", expand=True, padx=8, pady=8)
    main_scroll.grid_columnconfigure(1, weight=1)

    populate_main_scroll()


def populate_main_scroll():
    if main_scroll is None:
        return

    for w in main_scroll.winfo_children():
        w.destroy()

    row = 0

    row = add_section(main_scroll, "激活状态", row)

    lic = state["lic"]
    status_int = None
    status_reason = None

    if lic:
        status_raw = lic.get("LicenseStatus", "")
        try:
            status_int = int(status_raw)
        except ValueError:
            pass

        status_text = LICENSE_STATUS_MAP.get(status_int, f"未知（{status_raw}）")
        if status_int == 1:
            status_color = "#4ADE80"
        elif status_int in (2, 3, 4, 5, 6):
            status_color = "#FFB84D"
        else:
            status_color = "#FF5555"

        row = add_row(main_scroll, "许可证状态", status_text, row, status_color)

        name = lic.get("Name", "N/A")
        row = add_row(main_scroll, "产品名称", name, row)

        desc = lic.get("Description", "N/A")
        row = add_row(main_scroll, "产品描述", desc, row)

        channel_raw = lic.get("ProductKeyChannel", "")
        channel_text = CHANNEL_MAP.get(channel_raw, channel_raw if channel_raw else "N/A")
        row = add_row(main_scroll, "许可证渠道", channel_text, row)

        partial = lic.get("PartialProductKey", "N/A")
        row = add_row(main_scroll, "部分产品密钥", f"*****-*****-*****-*****-{partial}", row)

        grace = lic.get("GracePeriodRemaining", "")
        if grace:
            try:
                grace_min = int(grace)
                if grace_min > 0:
                    days = grace_min // 1440
                    hours = (grace_min % 1440) // 60
                    grace_text = f"{days} 天 {hours} 小时"
                else:
                    grace_text = "无宽限期（永久激活或已过期）"
            except ValueError:
                grace_text = grace
        else:
            grace_text = "N/A"
        row = add_row(main_scroll, "剩余宽限期", grace_text, row)

        reason_raw = lic.get("LicenseStatusReason", "0")
        try:
            status_reason = int(reason_raw)
        except ValueError:
            status_reason = 0

        reason_text = "无" if status_reason == 0 else f"0x{status_reason:08X}"
        if status_reason != 0:
            row = add_row(main_scroll, "状态原因码", reason_text, row, "#FFB84D")
    else:
        row = add_row(main_scroll, "许可证状态", "无法获取激活信息", row, "#FF5555")

    row = add_section(main_scroll, "KMS 信息", row)

    kms = state["kms"]
    if kms:
        kms_machine = kms.get("KeyManagementServiceMachine", "").strip()
        row = add_row(
            main_scroll, "已配置 KMS 服务器",
            kms_machine if kms_machine else "未配置", row,
            "#4ADE80" if kms_machine else "#8899AA",
        )

        kms_port = kms.get("KeyManagementServicePort", "").strip()
        row = add_row(
            main_scroll, "KMS 端口",
            kms_port if kms_port else "未配置", row,
        )

        discovered = kms.get("DiscoveredKeyManagementServiceMachineName", "").strip()
        row = add_row(
            main_scroll, "DNS 发现的 KMS",
            discovered if discovered else "未发现", row,
        )

        disc_port = kms.get("DiscoveredKeyManagementServiceMachinePort", "").strip()
        row = add_row(
            main_scroll, "DNS 发现端口",
            disc_port if disc_port else "未发现", row,
        )
    else:
        row = add_row(main_scroll, "KMS 信息", "无法获取", row, "#FF5555")

    row = add_section(main_scroll, "错误诊断", row)

    if status_int is not None and status_int != 1:
        if status_reason and status_reason != 0:
            error_text = decode_error(str(status_reason))
            row = add_row(main_scroll, "错误分析", error_text, row, "#FF8888")
        else:
            row = add_row(main_scroll, "错误分析", "系统未返回具体错误码", row, "#8899AA")
    elif status_int == 1:
        if status_reason and status_reason != 0:
            error_text = decode_error(str(status_reason))
            row = add_row(main_scroll, "状态提示", error_text, row, "#8899AA")
        else:
            row = add_row(main_scroll, "状态提示", "系统运行正常", row, "#4ADE80")
    else:
        row = add_row(main_scroll, "错误分析", "无法获取状态信息", row, "#FF5555")

    row = add_section(main_scroll, "操作建议", row)

    if status_int == 1:
        suggestion = "当前系统已正常激活"
        suggestion_color = "#4ADE80"
    elif status_int in (2, 3, 4):
        suggestion = "系统处于宽限期，请尽快使用正版密钥完成激活。"
        suggestion_color = "#FFB84D"
    elif status_int == 5:
        suggestion = "系统已进入通知状态，激活已失效，请重新激活。"
        suggestion_color = "#FF5555"
    elif status_int == 6:
        suggestion = "系统处于延长宽限期，建议尽快完成激活。"
        suggestion_color = "#FFB84D"
    else:
        suggestion = "请以管理员身份运行本工具以获取完整的激活信息。"
        suggestion_color = "#FF5555"

    sug_label = ctk.CTkLabel(
        main_scroll, text=suggestion, text_color=suggestion_color,
        font=ctk.CTkFont(size=12), anchor="w",
        wraplength=540, justify="left",
    )
    sug_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=(30, 20), pady=(4, 20))


build_main_ui()


splash = ctk.CTkFrame(app, fg_color="#0B1020", corner_radius=0)
splash.place(x=0, y=0, relwidth=1, relheight=1)

splash_box = ctk.CTkFrame(splash, fg_color="transparent")
splash_box.place(relx=0.5, rely=0.44, anchor="center")

ctk.CTkLabel(
    splash_box, text="激活识别工具",
    font=ctk.CTkFont(size=26, weight="bold"),
    text_color="#FFFFFF",
).pack(pady=(0, 8))

ctk.CTkLabel(
    splash_box, text="识别激活码、激活状态及常见错误",
    font=ctk.CTkFont(size=12),
    text_color="#4A5A78",
).pack(pady=(0, 46))

splash_step = ctk.CTkLabel(
    splash_box, text="正在启动",
    font=ctk.CTkFont(size=12),
    text_color="#8899AA",
)
splash_step.pack(pady=(0, 12))

splash_bar = ctk.CTkProgressBar(
    splash_box, width=360, height=6, corner_radius=3,
    progress_color="#3187FF", fg_color="#182238",
)
splash_bar.set(0)
splash_bar.pack()

splash_pct = ctk.CTkLabel(
    splash_box, text="0%",
    font=ctk.CTkFont(size=14, weight="bold"),
    text_color="#3187FF",
)
splash_pct.pack(pady=(14, 0))


def advance_progress():
    if state["splash_closed"]:
        return

    if state["percent"] < 100:
        state["percent"] += 1
        splash_bar.set(state["percent"] / 100)
        splash_pct.configure(text=f"{state['percent']}%")

    if state["percent"] >= 100 and state["task_done"]:
        state["splash_closed"] = True
        app.after(200, finish_loading)
        return

    app.after(random.randint(80, 120), advance_progress)


def finish_loading():
    app.attributes("-alpha", 0.0)
    splash.destroy()
    populate_main_scroll()
    fade_in_window(0.0)


def fade_in_window(alpha):
    if alpha > 1.0:
        alpha = 1.0
    app.attributes("-alpha", alpha)
    if alpha >= 1.0:
        return
    app.after(20, lambda: fade_in_window(alpha + 0.08))


def startup_worker(q):
    q.put(("step", "正在读取激活状态"))
    try:
        state["lic"] = check_activation_status()
    except Exception:
        state["lic"] = {}

    q.put(("step", "正在读取 KMS 信息"))
    try:
        state["kms"] = get_kms_info()
    except Exception:
        state["kms"] = {}

    q.put(("step", "正在生成界面"))
    q.put(("done", None))


def startup_poll(q):
    try:
        while True:
            item = q.get_nowait()
            k = item[0]
            if k == "step":
                splash_step.configure(text=item[1])
            elif k == "done":
                state["task_done"] = True
                return
    except queue.Empty:
        pass
    app.after(30, lambda: startup_poll(q))


app.after(random.randint(80, 120), advance_progress)

startup_q = queue.Queue()
threading.Thread(target=startup_worker, args=(startup_q,), daemon=True).start()
app.after(60, lambda: startup_poll(startup_q))

app.mainloop()