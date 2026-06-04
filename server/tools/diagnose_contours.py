import cv2
import numpy as np
from skimage.metrics import structural_similarity

ref = cv2.imread("data/uploads/artifacts/f86cb2/golden_left_f86cb2_1778823519555.png")
cur = cv2.imread("data/uploads/artifacts/f86cb2/final_aligned_f86cb2_1778824053659.png")

h, w = ref.shape[:2]
print(f"Image size: {w}x{h}")
print(f"min_area (current 0.0005) : {max(500, h*w*0.0005):.0f} px2")
print(f"min_area (proposed 0.00015): {max(500, h*w*0.00015):.0f} px2")

gray_ref = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
gray_cur = cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY)
_, diff = structural_similarity(gray_ref, gray_cur, full=True, win_size=7)
diff_uint8 = ((1.0 - diff) * 255).astype(np.uint8)

blurred = cv2.GaussianBlur(diff_uint8, (5,5), 0)
otsu_val, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
print(f"Otsu: {otsu_val}")
kernel_s = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
kernel_b = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7,7))
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel_s, iterations=2)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_b, iterations=2)

contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
all_c = sorted(contours, key=cv2.contourArea, reverse=True)

thr_old = max(500, h*w*0.0005)
thr_new = max(500, h*w*0.00015)

print(f"\nAll {len(all_c)} contours:")
print(f"{'#':>3}  {'area':>8}  {'w':>5}  {'h':>5}  {'cx':>5}  {'cy':>5}  old  new")
print("-"*58)
for i, c in enumerate(all_c[:50]):
    bx, by, bw, bh = cv2.boundingRect(c)
    area = cv2.contourArea(c)
    cx = bx + bw//2
    cy = by + bh//2
    p_old = "PASS" if area > thr_old else "MISS"
    p_new = "pass" if area > thr_new else "miss"
    print(f"{i:>3}  {area:>8.0f}  {bw:>5}  {bh:>5}  {cx:>5}  {cy:>5}  {p_old}  {p_new}")
