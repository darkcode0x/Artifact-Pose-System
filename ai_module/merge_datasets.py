"""
Merge 2 dataset Roboflow vao 1 thu muc chung.

Dac thu:
  - Dataset A (Lable_Bouding.yolov8_20_04): 9 classes - bi danh nham
      names: ['0_material_loss','1_peel','2_scratch','3_fold',
              '4_writing_marks','5_dirt','6_staning','7_burn_marks','writing_marks']
      => class 8 ('writing_marks') la trung voi class 4 ('4_writing_marks')
      => REMAP class 8 -> 4, giu 8 classes chuan

  - Dataset B (datatest_20_04): 8 classes dung chuan
      names: ['0_material_loss','1_peel','2_scratch','3_fold',
              '4_writing_marks','5_dirt','6_staning','7_burn_marks']

  - Ca 2 dataset chi co thu muc 'train/' (khong co valid/test - da check)

Output: Lable_Bouding.yolov8_merged/train/images + labels
        (de prepare_dataset_1804.py tu chia lai stratified 70/15/15)

Chay:
  python merge_datasets.py
"""

import os
import shutil

# ===================== CONFIG =====================
DATASET_A = "Lable_Bouding.yolov8_20_04"  # 9 classes (co class 8 bi trung)
DATASET_B = "datatest_20_04"               # 8 classes chuan

OUTPUT_DIR = "Lable_Bouding.yolov8_merged/train"

# Chi co thu muc train (da xac nhan tu cau truc thu muc)
SPLITS = ["train"]

# Remap class sai: class 8 (writing_marks trung) -> class 4 (4_writing_marks)
# Chi ap dung cho Dataset A
REMAP_A = {8: 4}

# 8 classes chuan
CLASS_NAMES = {
    0: "material_loss",
    1: "peel",
    2: "scratch",
    3: "fold",
    4: "writing_marks",
    5: "dirt",
    6: "staning",
    7: "burn_marks",
}
VALID_CLASSES = set(CLASS_NAMES.keys())
# ===================================================


def fix_label_file(src_path, remap=None):
    """
    Doc label file, remap class neu can.
    Tra ve danh sach lines da fix.
    """
    fixed_lines = []
    stats = {"remapped": 0, "invalid_cls": 0, "bad_format": 0}

    with open(src_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 5:
                stats["bad_format"] += 1
                continue
            try:
                cls_id = int(parts[0])
                cx, cy, w, h = map(float, parts[1:5])
            except ValueError:
                stats["bad_format"] += 1
                continue

            # Remap neu can
            if remap and cls_id in remap:
                cls_id = remap[cls_id]
                stats["remapped"] += 1

            # Bo qua class khong hop le
            if cls_id not in VALID_CLASSES:
                stats["invalid_cls"] += 1
                continue

            fixed_lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    return fixed_lines, stats


def collect_and_copy(dataset_dir, prefix, out_img_dir, out_lbl_dir, remap=None):
    """
    Thu thap anh + label tu 1 dataset, fix label, copy vao output.
    """
    total_copied = 0
    total_skipped = 0
    total_remapped = 0
    total_invalid = 0

    for split in SPLITS:
        img_dir = os.path.join(dataset_dir, split, "images")
        lbl_dir = os.path.join(dataset_dir, split, "labels")

        if not os.path.isdir(img_dir):
            print(f"  [SKIP] Khong tim thay: {img_dir}")
            continue
        if not os.path.isdir(lbl_dir):
            print(f"  [SKIP] Khong tim thay: {lbl_dir}")
            continue

        imgs = sorted([f for f in os.listdir(img_dir)
                       if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

        for img_fn in imgs:
            stem = os.path.splitext(img_fn)[0]
            ext = os.path.splitext(img_fn)[1]
            lbl_fn = stem + ".txt"
            lbl_path = os.path.join(lbl_dir, lbl_fn)

            if not os.path.exists(lbl_path):
                total_skipped += 1
                continue

            # Fix label
            fixed_lines, stats = fix_label_file(lbl_path, remap=remap)
            total_remapped += stats["remapped"]
            total_invalid += stats["invalid_cls"]

            if not fixed_lines:
                total_skipped += 1
                continue  # Khong con bbox hop le sau khi fix

            # Ten moi: prefix + split + stem (tranh trung ten giua 2 dataset)
            new_stem = f"{prefix}_{split}_{stem}"

            # Copy anh
            shutil.copy2(
                os.path.join(img_dir, img_fn),
                os.path.join(out_img_dir, new_stem + ext)
            )

            # Ghi label da fix
            with open(os.path.join(out_lbl_dir, new_stem + ".txt"), "w") as f:
                f.write("\n".join(fixed_lines))

            total_copied += 1

    return total_copied, total_skipped, total_remapped, total_invalid


def merge():
    out_img = os.path.join(OUTPUT_DIR, "images")
    out_lbl = os.path.join(OUTPUT_DIR, "labels")

    # Xoa output cu neu ton tai
    merged_root = os.path.dirname(OUTPUT_DIR)
    if os.path.exists(merged_root):
        shutil.rmtree(merged_root)

    os.makedirs(out_img, exist_ok=True)
    os.makedirs(out_lbl, exist_ok=True)

    print("=" * 65)
    print("MERGE 2 DATASETS -> 8 CLASSES CHUAN")
    print("=" * 65)

    grand_total = 0

    # --- Dataset A (9 classes, remap class 8 -> 4) ---
    print(f"\n[A] {DATASET_A}")
    print(f"    9 classes -> remap class 8 (writing_marks) -> class 4")
    if not os.path.isdir(DATASET_A):
        print(f"    [ERROR] Khong tim thay thu muc: {DATASET_A}")
    else:
        copied, skipped, remapped, invalid = collect_and_copy(
            DATASET_A, "A", out_img, out_lbl, remap=REMAP_A
        )
        print(f"    Copied:   {copied} anh")
        print(f"    Skipped:  {skipped} anh (khong co label hoac rong)")
        print(f"    Remapped: {remapped} bbox (class 8 -> 4)")
        print(f"    Invalid:  {invalid} bbox bi xoa (class khong hop le)")
        grand_total += copied

    # --- Dataset B (8 classes, dung chuan) ---
    print(f"\n[B] {DATASET_B}")
    print(f"    8 classes chuan, khong can remap")
    if not os.path.isdir(DATASET_B):
        print(f"    [ERROR] Khong tim thay thu muc: {DATASET_B}")
    else:
        copied, skipped, remapped, invalid = collect_and_copy(
            DATASET_B, "B", out_img, out_lbl, remap=None
        )
        print(f"    Copied:   {copied} anh")
        print(f"    Skipped:  {skipped} anh (khong co label hoac rong)")
        grand_total += copied

    print(f"\n{'='*65}")
    print(f"TONG CONG: {grand_total} anh da merge vao:")
    print(f"  {os.path.abspath(out_img)}")
    print(f"  {os.path.abspath(out_lbl)}")
    print(f"{'='*65}")
    print(f"""
Buoc tiep theo:
  1. Mo prepare_dataset_1804.py
  2. Doi dong SRC_DIR thanh:
       SRC_DIR = "Lable_Bouding.yolov8_merged"
  3. Chay: python prepare_dataset_1804.py
""")


if __name__ == "__main__":
    merge()