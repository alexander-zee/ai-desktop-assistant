import os
import time
import base64
import json
from io import BytesIO
from PIL import Image, ImageTk, ImageDraw
import mss
import tkinter as tk
import threading
from openai import OpenAI
import win32api
import win32con

# ---------------- CONFIG ---------------- #
ASSISTANT_NAME = "ODOO AI"
UPDATE_INTERVAL = 30  # seconds
ICON_PATH = r"C:\Users\Alexa\Desktop\Finance Matters Bestanden\ODOO AI\ODOO_AI_LOGO.png"
PADDING_X = 20
PADDING_Y = 50
DEBUG_MODEL_IO = False  # Set to True to log model input/output for debugging
PRIMARY_MODEL = "gpt-5-mini"
FALLBACK_MODEL = "gpt-4.1-mini"
# ---------------------------------------- #

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("⚠️ No OpenAI API key found. Use: setx OPENAI_API_KEY \"your-key\"")

client = OpenAI(api_key=api_key)

# ---------- Smoke test and warm-up ---------- #
def debug_test_text_only():
    """Quick smoke test to verify model/key works without images."""
    try:
        resp = client.responses.create(
            model=PRIMARY_MODEL,
            input="What is 1+1?"
        )
        output = resp.output_text if hasattr(resp, 'output_text') else ""
        print(f"[SMOKE TEST] Model: {PRIMARY_MODEL}, Output: {output}")
        if not output:
            # Try fallback
            try:
                resp = client.responses.create(
                    model=FALLBACK_MODEL,
                    input="What is 1+1?"
                )
                output = resp.output_text if hasattr(resp, 'output_text') else ""
                print(f"[SMOKE TEST] Fallback model: {FALLBACK_MODEL}, Output: {output}")
            except Exception as e:
                print(f"[SMOKE TEST] Fallback model also failed: {e}")
    except Exception as e:
        print(f"[SMOKE TEST] Failed: {e}")

def warm_up_model():
    try:
        _ = client.responses.create(
            model=PRIMARY_MODEL,
            input="warmup",
            max_output_tokens=1
        )
    except Exception:
        pass

# ---------- Utility ---------- #
def extract_text_from_content(content) -> str:
    """
    Robustly extract text from OpenAI model response content.
    Handles multiple formats:
    - content is a string
    - content is a list of dict blocks, e.g. {"type":"text","text":"..."}
    - content is a list of objects/blocks (newer OpenAI SDK style) with .type and .text attributes
    - content is missing or None
    
    Returns: trimmed string, or "" if nothing is found.
    """
    if content is None:
        return ""
    
    if isinstance(content, str):
        return content.strip()
    
    if isinstance(content, list):
        parts = []
        for part in content:
            text_val = None
            
            # Handle dict format: {"type": "text", "text": "..."}
            if isinstance(part, dict):
                if part.get("type") == "text":
                    text_val = part.get("text", "")
            
            # Handle object format (newer SDK style) with .type and .text attributes
            elif hasattr(part, "type") and hasattr(part, "text"):
                if getattr(part, "type", None) == "text":
                    text_val = getattr(part, "text", "")
            
            # Fallback: try to get "text" attribute directly
            elif hasattr(part, "text"):
                text_val = getattr(part, "text", "")
            
            if text_val:
                text_val = str(text_val).strip()
                if text_val:
                    parts.append(text_val)
        
        return " ".join(parts).strip()
    
    # Fallback: try to convert to string
    try:
        return str(content).strip()
    except Exception:
        return ""

def prepare_image_for_upload(img) -> bytes:
    """
    Optimize screenshot for upload by resizing and compressing.
    - Resize width to <= 1024px while preserving aspect ratio
    - Encode as JPEG quality ~70 instead of PNG
    
    Returns: bytes of the optimized image
    """
    # Resize if width > 1024
    width, height = img.size
    if width > 1024:
        ratio = 1024 / width
        new_width = 1024
        new_height = int(height * ratio)
        img = img.resize((new_width, new_height), Image.LANCZOS)
    
    # Convert to RGB if necessary (JPEG doesn't support transparency)
    if img.mode in ("RGBA", "LA", "P"):
        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        rgb_img.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = rgb_img
    elif img.mode != "RGB":
        img = img.convert("RGB")
    
    # Save as JPEG with quality 70
    buffered = BytesIO()
    img.save(buffered, format="JPEG", quality=70, optimize=True)
    return buffered.getvalue()

def capture_screen():
    """Capture a reduced-size central region of the screen (for faster upload)."""
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        width, height = monitor["width"], monitor["height"]
        region = {
            "top": height // 4,
            "left": width // 4,
            "width": width // 2,
            "height": height // 2
        }
        shot = sct.grab(region)
        return Image.frombytes("RGB", shot.size, shot.rgb)

def get_active_window_title():
    try:
        import win32gui
        return win32gui.GetWindowText(win32gui.GetForegroundWindow())
    except Exception:
        return "Unknown window"

def analyze_screen(img):
    """Send screen image to GPT-5 for one concise, screen-based observation."""
    img_bytes = prepare_image_for_upload(img)
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")

    prompt = (
        f"You are {ASSISTANT_NAME}, an accounting/Odoo assistant. You can SEE the screenshot. "
        f"Write ONE short, concrete sentence about what is visible on the screen. "
        f"It must be based on visible UI elements only (e.g. Odoo views, invoices, lists, code editors, filenames, buttons). "
        f"Avoid generic advice or productivity tips. Be specific and refer to what you see. "
        f"Active window title: '{get_active_window_title()}'."
    )

    try:
        # Try primary model first
        resp = client.responses.create(
            model=PRIMARY_MODEL,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{img_b64}"}
                ]
            }],
            max_output_tokens=50
        )

        text = resp.output_text if hasattr(resp, 'output_text') else ""
        if text:
            text = text.strip()
        
        # Debug logging
        if DEBUG_MODEL_IO:
            print(f"[DEBUG analyze_screen] output_text: {text[:300] if text else '(empty)'}")
            if not text:
                try:
                    if hasattr(resp, 'model_dump'):
                        resp_repr = json.dumps(resp.model_dump(), default=str, indent=2)[:500]
                    else:
                        resp_repr = json.dumps(resp.__dict__, default=str, indent=2)[:500]
                    print(f"[DEBUG analyze_screen] full response structure: {resp_repr}")
                except Exception:
                    print(f"[DEBUG analyze_screen] full response structure: {repr(resp)[:500]}")

        # If empty, try fallback model
        if not text:
            print("analyze_screen: empty content from model, trying fallback")
            try:
                resp = client.responses.create(
                    model=FALLBACK_MODEL,
                    input=[{
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": f"data:image/jpeg;base64,{img_b64}"}
                        ]
                    }],
                    max_output_tokens=50
                )
                text = resp.output_text if hasattr(resp, 'output_text') else ""
                if text:
                    text = text.strip()
                    print(f"[FALLBACK] analyze_screen succeeded with {FALLBACK_MODEL}")
            except Exception as e:
                print(f"[FALLBACK] analyze_screen error: {e}")

        # If still empty, return error
        if not text:
            print("analyze_screen: empty content from model (both primary and fallback)")
            return "⚠️ Unable to analyze screen — model returned empty response"

        return text

    except Exception as e:
        # Log the error, but don't spam the UI
        print(f"analyze_screen error: {e}")
        return None


# ---------- Gradient + Rounded ---------- #
def make_diagonal_gradient(w, h, radius=25):
    # Supersampled draw to avoid dark ridges and jagged corners
    scale = 2
    W, H = w * scale, h * scale
    img2x = Image.new("RGBA", (W, H), (1, 2, 3, 0))  # fully transparent outside
    draw = ImageDraw.Draw(img2x)
    for x in range(W):
        for y in range(H):
            mix = (x * 0.8 + y * 0.2) / (W + H)
            # Odoo-like dark gray gradient
            r1, g1, b1 = (60, 64, 75)     # lighter gray
            r2, g2, b2 = (30, 33, 41)     # darker gray
            r = int(r1 + (r2 - r1) * mix)
            g = int(g1 + (g2 - g1) * mix)
            b = int(b1 + (b2 - b1) * mix)
            draw.point((x, y), fill=(r, g, b, 255))
    mask2x = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask2x).rounded_rectangle([0, 0, W, H], radius * scale, fill=255)
    img2x.putalpha(mask2x)
    # Downsample with high-quality filter
    img = img2x.resize((w, h), Image.LANCZOS)
    return img

# ---------- UI / Overlay ---------- #
def start_overlay(get_message_func):
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.title(f"{ASSISTANT_NAME}Overlay")
    root.wm_attributes("-transparentcolor", "#010203")  # for alpha edges

    WIDTH, HEIGHT = int(420 * 1.5), int(220 * 1.5)  # Increased height for text display

    # --- Determine right-side initial position --- #
    def get_monitor_work_area_for_window(hwnd):
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        info = win32api.GetMonitorInfo(monitor)
        work_left, work_top, work_right, work_bottom = info.get("Work")
        return work_left, work_top, work_right, work_bottom

    root.update_idletasks()
    hwnd_temp = root.winfo_id()
    work_l, work_t, work_r, work_b = get_monitor_work_area_for_window(hwnd_temp)
    start_x = max(work_l, work_r - WIDTH - PADDING_X)
    start_y = work_t + ((work_b - work_t - HEIGHT) // 2)
    root.geometry(f"{WIDTH}x{HEIGHT}+{start_x}+{start_y}")

    # --- Gradient background with clean rounded corners --- #
    bg_img = make_diagonal_gradient(WIDTH, HEIGHT)
    bg_photo = ImageTk.PhotoImage(bg_img)

    canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT,
                       highlightthickness=0, bg="#010203", bd=0)
    canvas.pack(fill="both", expand=True)
    canvas.create_image(0, 0, anchor="nw", image=bg_photo)

    # --- Icon and text --- #
    icon_photo = None
    if os.path.exists(ICON_PATH):
        icon = Image.open(ICON_PATH).convert("RGBA").resize((int(64 * 1.2), int(64 * 1.2)))
        datas = icon.getdata()
        icon.putdata([(r, g, b, 0) if r > 240 and g > 240 and b > 240 else (r, g, b, a)
                      for (r, g, b, a) in datas])
        icon_photo = ImageTk.PhotoImage(icon)
        canvas.create_image(45, HEIGHT // 2, anchor="w", image=icon_photo)

    canvas.create_text(125, 24, text=ASSISTANT_NAME,
                       fill="white", font=("Segoe UI Semibold", 13), anchor="nw")
    message_text = canvas.create_text(
        125,
        48,
        text=f"{ASSISTANT_NAME} active",
        fill="white",
        font=("Segoe UI", 11),
        anchor="nw",
        width=WIDTH - 180
    )

    # --- Output box (read-only) --- #
    output_box = tk.Text(
        root,
        bg="#20232b",
        fg="#FFFFFF",
        wrap="word",
        relief="flat",
        font=("Segoe UI", 11),
        height=4,
        bd=0
    )
    output_box.place(x=125, y=72, width=WIDTH - 180, height=70)
    output_box.configure(state=tk.DISABLED)

    def set_output_text(text: str):
        output_box.configure(state=tk.NORMAL)
        output_box.delete("1.0", "end")
        output_box.insert("1.0", text)
        output_box.configure(state=tk.DISABLED)

    # --- Chat input textbox (bottom) --- #
    chat_box = tk.Text(
        root,
        bg="#20232b",
        fg="#FFFFFF",
        wrap="word",
        relief="flat",
        font=("Segoe UI", 11),
        insertbackground="#FFFFFF",
        height=2,
        bd=0
    )
    chat_box.place(
        x=125,
        y=HEIGHT - 60,
        width=WIDTH - 180,
        height=40
    )
    chat_box.focus_set()

    # Idle timer variables
    last_user_input_time = time.time()
    is_busy = False

    def on_chat_enter(event=None):
        nonlocal last_user_input_time, is_busy
        if event.state & 0x0001:  # Shift pressed
            return
        text = chat_box.get("1.0", "end").strip()
        if not text:
            return "break"
        print(f"🟢 User input detected: {text}")
        last_user_input_time = time.time()
        is_busy = True
        chat_box.delete("1.0", "end")
        set_output_text(f"{ASSISTANT_NAME} is thinking...")

        def send_chat_message(user_input):
            nonlocal is_busy
            try:
                img = capture_screen()
                img_bytes = prepare_image_for_upload(img)
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")

                system_prompt = (
                    f"You are {ASSISTANT_NAME}, an intelligent on-screen assistant. "
                    f"You can SEE the user's current screen image; base your responses on what is visibly present "
                    f"(Odoo windows, invoices, code editors, filenames, UI elements, etc.) plus the user's question. "
                    f"Avoid generic coaching or vague advice like 'stay focused' or 'double-check everything' "
                    f"unless the screen truly provides no useful cues. "
                    f"Keep replies focused and concise: ideally 1–3 short sentences directly about what is on screen "
                    f"and how it relates to the user's request."
                )

                # Try primary model first
                resp = client.responses.create(
                    model=PRIMARY_MODEL,
                    input=[
                        {
                            "role": "system",
                            "content": [{"type": "input_text", "text": system_prompt}]
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": user_input},
                                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{img_b64}"}
                            ]
                        }
                    ],
                    max_output_tokens=250
                )

                reply = resp.output_text if hasattr(resp, 'output_text') else ""
                if reply:
                    reply = reply.strip()
                
                # Debug logging
                if DEBUG_MODEL_IO:
                    print(f"[DEBUG send_chat_message] output_text: {reply[:300] if reply else '(empty)'}")
                    if not reply:
                        try:
                            if hasattr(resp, 'model_dump'):
                                resp_repr = json.dumps(resp.model_dump(), default=str, indent=2)[:500]
                            else:
                                resp_repr = json.dumps(resp.__dict__, default=str, indent=2)[:500]
                            print(f"[DEBUG send_chat_message] full response structure: {resp_repr}")
                        except Exception:
                            print(f"[DEBUG send_chat_message] full response structure: {repr(resp)[:500]}")

                # If empty, try fallback model
                if not reply:
                    print("send_chat_message: empty content from model, trying fallback")
                    try:
                        resp = client.responses.create(
                            model=FALLBACK_MODEL,
                            input=[
                                {
                                    "role": "system",
                                    "content": [{"type": "input_text", "text": system_prompt}]
                                },
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "input_text", "text": user_input},
                                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{img_b64}"}
                                    ]
                                }
                            ],
                            max_output_tokens=250
                        )
                        reply = resp.output_text if hasattr(resp, 'output_text') else ""
                        if reply:
                            reply = reply.strip()
                            print(f"[FALLBACK] send_chat_message succeeded with {FALLBACK_MODEL}")
                    except Exception as e:
                        print(f"[FALLBACK] send_chat_message error: {e}")

                # If still empty, return clear error message
                if not reply:
                    print("send_chat_message: empty content from model (both primary and fallback)")
                    reply = "⚠️ Unable to process request — model returned empty response. Please try again."

                print(f"💬 {ASSISTANT_NAME} replied: {reply}")
            except Exception as e:
                reply = f"⚠️ {e}"
                print(f"Exception in send_message: {e}")

            root.after(0, lambda: set_output_text(reply))
            root.after(0, lambda: set_message('💬 Chat active'))
            is_busy = False

        threading.Thread(target=send_chat_message, args=(text,), daemon=True).start()
        return "break"

    chat_box.bind("<Return>", on_chat_enter)
    chat_box.bind("<KP_Enter>", on_chat_enter)

    # Idle screen observation function
    def check_idle_and_update():
        nonlocal last_user_input_time, is_busy
        if not is_busy and time.time() - last_user_input_time > 15:
            try:
                img = capture_screen()
                obs = analyze_screen(img)
                if obs:
                    root.after(0, lambda: set_output_text(obs))
                    root.after(0, lambda: set_message("💬 Screen observation"))
            except Exception as e:
                print(f"Idle update error: {e}")
        
        # Schedule next check
        root.after(15000, check_idle_and_update)  # Check every 15 seconds

    # --- Pop-out animation state ---
    pop_running = {"active": False}

    def animate_pop():
        if pop_running["active"]:
            return
        pop_running["active"] = True
        # Capture current window geometry and center
        geom = root.geometry().split("+")
        win_w, win_h = WIDTH, HEIGHT
        win_x, win_y = int(geom[1]), int(geom[2])
        cx = win_x + win_w // 2
        cy = win_y + win_h // 2

        frames = 6
        duration_ms = 300
        dt = max(1, duration_ms // frames)
        peak = 1.06  # ~6% scale up
        scales = []
        for i in range(frames):
            t = (i + 1) / frames
            if t <= 0.5:
                s = 1.0 + (peak - 1.0) * (t / 0.5)
            else:
                s = peak - (peak - 1.0) * ((t - 0.5) / 0.5)
            scales.append(s)

        def step(i=0):
            if i >= len(scales):
                root.geometry(f"{win_w}x{win_h}+{win_x}+{win_y}")
                pop_running["active"] = False
                return
            s = scales[i]
            new_w = int(win_w * s)
            new_h = int(win_h * s)
            new_x = int(cx - new_w / 2)
            new_y = int(cy - new_h / 2)
            root.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")
            root.after(dt, lambda: step(i + 1))

        step()

    # --- Window fade (entire overlay) ---
    overlay_fade_duration_s = 28.0
    overlay_min_alpha = 0.18
    last_overlay_reset_time = time.time()

    def window_fade_tick():
        elapsed = time.time() - last_overlay_reset_time
        if elapsed <= 0:
            alpha = 1.0
        else:
            t = min(1.0, elapsed / overlay_fade_duration_s)
            alpha = max(overlay_min_alpha, 1.0 - t * (1.0 - overlay_min_alpha))
        try:
            root.attributes("-alpha", alpha)
        except Exception:
            pass
        finally:
            root.after(150, window_fade_tick)

    def set_message(text):
        nonlocal last_overlay_reset_time
        canvas.itemconfig(message_text, text=text)
        # Reset window alpha to full and trigger pop
        last_overlay_reset_time = time.time()
        try:
            root.attributes("-alpha", 1.0)
        except Exception:
            pass
        animate_pop()

    # --- Dragging --- #
    drag = {"offset_x": 0, "offset_y": 0, "moved": False}
    def on_press(e):
        geom = root.geometry().split("+")
        win_x, win_y = int(geom[1]), int(geom[2])
        drag["offset_x"] = e.x_root - win_x
        drag["offset_y"] = e.y_root - win_y
        drag["moved"] = False
    def on_motion(e):
        new_x = e.x_root - drag["offset_x"]
        new_y = e.y_root - drag["offset_y"]
        root.geometry(f"{WIDTH}x{HEIGHT}+{new_x}+{new_y}")
        drag["moved"] = True
    def on_release(e):
        nonlocal last_overlay_reset_time
        if not drag["moved"]:
            print("🟢 Click detected on overlay")
            # Reset window alpha fully on click
            last_overlay_reset_time = time.time()
            try:
                root.attributes("-alpha", 1.0)
            except Exception:
                pass
            # Focus chat input instead of opening panel
            chat_box.focus_force()
    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_motion)
    canvas.bind("<ButtonRelease-1>", on_release)

    # Optional polish: reset to full on hover
    def on_enter(_):
        nonlocal last_overlay_reset_time
        last_overlay_reset_time = time.time()
        try:
            root.attributes("-alpha", 1.0)
        except Exception:
            pass
    canvas.bind("<Enter>", on_enter)

    # --- Fade-in animation (window alpha) ---
    def fade_in():
        try:
            current = float(root.attributes("-alpha")) if root.attributes("-alpha") else 1.0
        except Exception:
            current = 0.0
        target = 1.0
        steps = 12
        duration = 0.30
        dt = duration / steps
        for i in range(steps + 1):
            a = current + (target - current) * (i / steps)
            root.attributes("-alpha", max(0.0, min(1.0, a)))
            root.update_idletasks()
            time.sleep(dt)

    root.attributes("-alpha", 1.0)

    # --- Periodic update --- #
    def update_loop(first_run=False):
        if first_run:
            set_message("Starting up... Preparing model.")
            threading.Thread(target=debug_test_text_only, daemon=True).start()
            threading.Thread(target=warm_up_model, daemon=True).start()
            root.after(5000, lambda: fetch_and_reschedule())
            return
        fetch_and_reschedule()

    def fetch_and_reschedule():
        try:
            msg = get_message_func()
            if msg:
                print(f"📝 New observation: {msg}")
                set_message(msg)
            else:
                print("… no change")
        except Exception as e:
            err = f"⚠️ {e}"
            print(err)
            set_message(err)
        finally:
            root.after(UPDATE_INTERVAL * 1000, update_loop)

    # Start loops
    window_fade_tick()
    update_loop(first_run=True)
    check_idle_and_update()  # Start idle timer for screen observations

    root.mainloop()

# ---------- Main Loop ---------- #
def main_loop():
    last_text = ""

    def get_new_output():
        nonlocal last_text
        img = capture_screen()
        obs = analyze_screen(img)
        if not obs:
            return None
        if obs != last_text:
            last_text = obs
            return obs
        return None

    start_overlay(get_new_output)


if __name__ == "__main__":
    print(f"{ASSISTANT_NAME} active ✨")
    main_loop()
