# name_tag_bold_scaled_sub.py
import time
import framebuf
import epd2in13b_V4 as epd
import random

# --- Konfiguration ---
NAME = "UR NAME"        # Name display 
EMOJIS = ["^w^", "^w^", "x_x", "-_-", "o_o", ">w<", "GLaDOS" ] #<-- u can add new faces
SUBTEXT = random.choice(EMOJIS)        # Text unter dem Namen
SCALE = 4               # Scale for name
SUB_SCALE = 3          # Scale for Subtext
BOLD_PASSES = 3         # text 
MARGIN = 8
LINE_SPACING = 4

def bytes_for(width, height):
    row_bytes = (width + 7) // 8
    return row_bytes * height, row_bytes

# --- Display init (robust) ---
display = None
for cls_name in ("EPD_2in13_B_V4_Portrait", "EPD_2in13_B", "EPD_2in13_B_V4_Portrait"):
    if hasattr(epd, cls_name):
        try:
            display = getattr(epd, cls_name)()
            break
        except Exception:
            pass
if display is None:
    try:
        display = epd.EPD_2in13_B()
    except Exception as e:
        raise RuntimeError("Keine passende Display-Klasse gefunden: {}".format(e))

if hasattr(display, "init"):
    display.init()
try:
    display.Clear(0xFF, 0xFF)
except TypeError:
    try:
        display.Clear()
    except Exception:
        pass

W = getattr(display, "width", None) or getattr(epd, "EPD_WIDTH", None)
H = getattr(display, "height", None) or getattr(epd, "EPD_HEIGHT", None)
if not W or not H:
    raise RuntimeError("Display-Größe nicht ermittelbar")
print("Display:", W, "x", H)

# ensure display buffers
bufsize_disp, disp_row_bytes = bytes_for(W, H)
try:
    need_create = False
    if not hasattr(display, "imageblack") or not hasattr(display, "imagered"):
        need_create = True
    else:
        try:
            display.imageblack.fill(0xFF)
            display.imagered.fill(0xFF)
        except Exception:
            need_create = True
    if need_create:
        bbuf = bytearray(b'\xFF' * bufsize_disp)
        rbuf = bytearray(b'\xFF' * bufsize_disp)
        display.imageblack = framebuf.FrameBuffer(bbuf, W, H, framebuf.MONO_HLSB)
        display.imagered = framebuf.FrameBuffer(rbuf, W, H, framebuf.MONO_HLSB)
except Exception as e:
    raise RuntimeError("Fehler beim Vorbereiten der Display-Puffer: {}".format(e))

# --- Prepare temp buffers for main text and subtext ---
CHAR_W = 8
CHAR_H = 16

# Build lines: main name (single line) and subtext (single line)
main_line = NAME
sub_line = SUBTEXT

# compute unscaled sizes
main_w_un = len(main_line) * CHAR_W
main_h_un = CHAR_H
sub_w_un = len(sub_line) * CHAR_W
sub_h_un = CHAR_H

# scaled sizes
main_w = main_w_un * SCALE
main_h = main_h_un * SCALE
sub_w = sub_w_un * SUB_SCALE
sub_h = sub_h_un * SUB_SCALE

# total unscaled temp dims (stacked vertically with spacing)
temp_w_un = max(main_w_un, sub_w_un) + 2 * MARGIN
temp_h_un = main_h_un + sub_h_un + LINE_SPACING + 2 * MARGIN

# scaled final dims
scaled_w = temp_w_un * SCALE  # conservative: scale by main SCALE
# For height, main scaled by SCALE, sub scaled by SUB_SCALE -> compute exact
scaled_h = main_h + (sub_h * (SCALE // max(1, SUB_SCALE))) + (LINE_SPACING * SCALE) + 2 * MARGIN * SCALE
# To avoid complexity, create temp buffer using larger of scales to ensure fit
# Simpler approach: create separate temp buffers and compose into final scaled canvas.

# --- Create main temp FB (unscaled), draw main text ---
main_temp_w = main_w_un + 2 * MARGIN
main_temp_h = main_h_un + 2 * MARGIN
main_bytes = ((main_temp_w + 7) // 8) * main_temp_h
main_buf = bytearray(b'\xFF' * main_bytes)
main_fb = framebuf.FrameBuffer(main_buf, main_temp_w, main_temp_h, framebuf.MONO_HLSB)
main_fb.fill(1)

# Name zeichnen, aber S rot
for i, ch in enumerate(main_line):
    x = MARGIN + i * CHAR_W
    y = MARGIN

    if ch == "S":
        # S in ROT zeichnen → in main_fb NICHT zeichnen
        # Stattdessen später in imagered zeichnen
        tmp = framebuf.FrameBuffer(bytearray((CHAR_W*CHAR_H)//8), CHAR_W, CHAR_H, framebuf.MONO_HLSB)
        tmp.fill(1)
        tmp.text("S", 0, 0, 0)

        # Pixel in ROT speichern
        for sy in range(CHAR_H):
            for sx in range(CHAR_W):
                if tmp.pixel(sx, sy) == 0:
                    display.imagered.pixel(x + sx, y + sy, 0)
    else:
        # Normale Buchstaben in Schwarz
        main_fb.text(ch, x, y, 0)

# --- Create sub temp FB (unscaled), draw subtext ---
sub_temp_w = sub_w_un + 2 * MARGIN
sub_temp_h = sub_h_un + 2 * MARGIN
sub_bytes = ((sub_temp_w + 7) // 8) * sub_temp_h
sub_buf = bytearray(b'\xFF' * sub_bytes)
sub_fb = framebuf.FrameBuffer(sub_buf, sub_temp_w, sub_temp_h, framebuf.MONO_HLSB)
sub_fb.fill(1)
sub_fb.text(sub_line, MARGIN, MARGIN, 0)

# --- Scale main_fb and sub_fb into scaled canvases ---
scaled_main_w = main_temp_w * SCALE
scaled_main_h = main_temp_h * SCALE
scaled_main_bytes = ((scaled_main_w + 7) // 8) * scaled_main_h
scaled_main_buf = bytearray(b'\xFF' * scaled_main_bytes)
scaled_main_fb = framebuf.FrameBuffer(scaled_main_buf, scaled_main_w, scaled_main_h, framebuf.MONO_HLSB)
scaled_main_fb.fill(1)

for sy in range(main_temp_h):
    for sx in range(main_temp_w):
        if main_fb.pixel(sx, sy) == 0:
            base_x = sx * SCALE
            base_y = sy * SCALE
            for dy in range(SCALE):
                for dx in range(SCALE):
                    tx = base_x + dx
                    ty = base_y + dy
                    if 0 <= tx < scaled_main_w and 0 <= ty < scaled_main_h:
                        scaled_main_fb.pixel(tx, ty, 0)

scaled_sub_w = sub_temp_w * SUB_SCALE
scaled_sub_h = sub_temp_h * SUB_SCALE
scaled_sub_bytes = ((scaled_sub_w + 7) // 8) * scaled_sub_h
scaled_sub_buf = bytearray(b'\xFF' * scaled_sub_bytes)
scaled_sub_fb = framebuf.FrameBuffer(scaled_sub_buf, scaled_sub_w, scaled_sub_h, framebuf.MONO_HLSB)
scaled_sub_fb.fill(1)

for sy in range(sub_temp_h):
    for sx in range(sub_temp_w):
        if sub_fb.pixel(sx, sy) == 0:
            base_x = sx * SUB_SCALE
            base_y = sy * SUB_SCALE
            for dy in range(SUB_SCALE):
                for dx in range(SUB_SCALE):
                    tx = base_x + dx
                    ty = base_y + dy
                    if 0 <= tx < scaled_sub_w and 0 <= ty < scaled_sub_h:
                        scaled_sub_fb.pixel(tx, ty, 0)

# --- Compose final canvas (centered, main above sub) ---
# final canvas size: use display-oriented scaled area
if W < H:
    # portrait display -> we'll rotate later; final canvas size before rotation = H x W (landscape)
    canvas_w = H
    canvas_h = W
else:
    canvas_w = W
    canvas_h = H

final_bytes = ((canvas_w + 7) // 8) * canvas_h
final_buf = bytearray(b'\xFF' * final_bytes)
final_fb = framebuf.FrameBuffer(final_buf, canvas_w, canvas_h, framebuf.MONO_HLSB)
final_fb.fill(1)

# compute positions to center stacked main+sub vertically
total_h = scaled_main_h + (LINE_SPACING * SCALE) + scaled_sub_h
start_y = max(0, (canvas_h - total_h) // 2) - 15
start_x_main = max(0, (canvas_w - scaled_main_w) // 2)
start_x_sub = max(0, (canvas_w - scaled_sub_w) // 2)

# blit main
for y in range(scaled_main_h):
    for x in range(scaled_main_w):
        if scaled_main_fb.pixel(x, y) == 0:
            fx = start_x_main + x
            fy = start_y + y
            if 0 <= fx < canvas_w and 0 <= fy < canvas_h:
                final_fb.pixel(fx, fy, 0)

# blit sub below main
sub_start_y = start_y + scaled_main_h + (LINE_SPACING * SCALE) - 90 # Subtext Scale


for y in range(scaled_sub_h):
    for x in range(scaled_sub_w):
        if scaled_sub_fb.pixel(x, y) == 0:
            fx = start_x_sub + x
            fy = sub_start_y + y
            if 0 <= fx < canvas_w and 0 <= fy < canvas_h:
                final_fb.pixel(fx, fy, 0)

# Optional bold passes: overdraw final_fb into a bolder final_fb2
final2_bytes = ((canvas_w + 7) // 8) * canvas_h
final2_buf = bytearray(b'\xFF' * final2_bytes)
final2_fb = framebuf.FrameBuffer(final2_buf, canvas_w, canvas_h, framebuf.MONO_HLSB)
final2_fb.fill(1)

offsets = [(0,0)]
if BOLD_PASSES >= 2:
    offsets += [(1,0),(0,1)]
if BOLD_PASSES >= 4:
    offsets += [(-1,0),(0,-1)]
offsets = offsets[:BOLD_PASSES]

for ox, oy in offsets:
    for y in range(canvas_h):
        for x in range(canvas_w):
            if final_fb.pixel(x, y) == 0:
                tx = x + ox
                ty = y + oy
                if 0 <= tx < canvas_w and 0 <= ty < canvas_h:
                    final2_fb.pixel(tx, ty, 0)

# --- Map final2_fb into display.imageblack with rotation if needed ---
display.imageblack.fill(0xFF)
display.imagered.fill(0xFF)

if W >= H:
    # display is landscape or equal: center final2_fb on display
    start_dx = (W - canvas_w) // 2
    start_dy = (H - canvas_h) // 2
    for y in range(canvas_h):
        for x in range(canvas_w):
            if final2_fb.pixel(x, y) == 0:
                dx = start_dx + x
                dy = start_dy + y
                if 0 <= dx < W and 0 <= dy < H:
                    display.imageblack.pixel(dx, dy, 0)
else:
    # rotate 90 CW into portrait display: (x,y) -> (dx = y, dy = W-1-x)
    # center rotated image
    rot_w = canvas_h
    rot_h = canvas_w
    start_dx = (W - rot_w) // 2
    start_dy = (H - rot_h) // 2
    for y in range(canvas_h):
        for x in range(canvas_w):
            if final2_fb.pixel(x, y) == 0:
                dx0 = y
                dy0 = canvas_w - 1 - x
                dx = start_dx + dx0
                dy = start_dy + dy0
                if 0 <= dx < W and 0 <= dy < H:
                    display.imageblack.pixel(dx, dy, 0)
small_text = "Code by Joshkao" #<-- u can change it if u like

tmp_w = len(small_text) * CHAR_W
tmp_h = CHAR_H

buf = bytearray(tmp_w * tmp_h // 8)
fb = framebuf.FrameBuffer(buf, tmp_w, tmp_h, framebuf.MONO_HLSB)

fb.fill(1)
fb.text(small_text, 0, 0, 0)

# Position unten rechts
pos_x = W - tmp_h - 4
pos_y = H - tmp_w - 4

for y in range(tmp_h):
    for x in range(tmp_w):
        if fb.pixel(x, y) == 0:
            display.imagered.pixel(
                pos_x + y,
                pos_y + (tmp_w - 1 - x),
                0
            )
# --- Display with fallbacks ---
displayed = False
try:
    display.display()
    displayed = True
except Exception as e:
    print("display.display() warf:", e)
    try:
        display.display(display.imageblack, display.imagered)
        displayed = True
    except Exception as e2:
        print("display.display(imageblack,imagered) warf:", e2)
        try:
            display.display(display.getbuffer(display.imageblack), display.getbuffer(display.imagered))
            displayed = True
        except Exception as e3:
            print("Alle display-Aufrufe schlugen fehl:", e3)

if not displayed:
    raise RuntimeError("Anzeige konnte nicht aufgerufen werden. Siehe obige Fehlermeldungen.")

time.sleep(2)
if hasattr(display, "sleep"):
    display.sleep()
print("Name tag mit Subtext angezeigt.")


