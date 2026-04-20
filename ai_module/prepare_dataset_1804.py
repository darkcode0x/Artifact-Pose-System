"""
Prepare dataset 1804 cho bai toan DAMAGE DETECTION (8 classes).

Dac thu damage detection:
  - Dataset nho, patterns tinh te (scratch, dirt nho)
  - Class imbalance cao (fold 27% vs scratch 4.4%)
  - Can bbox nho de bat damage chi tiet

Pipeline:
  1. Lam sach labels:
     - Remap class 8 (trung) -> 4 (writing_marks)
     - Loc bbox qua lon (>90% anh) - chac chan sai
     - Loc bbox QUA nho (<0.02% anh) - YOLO khong detect duoc
     - Bo ANH KHONG co bbox hop le
     - Clamp bbox vao [0,1]
  2. Stratified split 70/15/15 - dam bao moi class deu co trong 3 splits
  3. Balance TRAIN SET bang augmentation (flip H/V/HV):
     - Target: dua moi class len muc median
     - KHONG augment val/test - giu phan phoi that
  4. Fix PNG iCCP profile sai
  5. Xuat data.yaml + zip

Chay:
  python prepare_dataset_1804.py
"""
import os
import sys
import shutil
import random
import zipfile
import warnings
from collections import Counter, defaultdict

# Windows UTF-8 + tat libpng warning
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
warnings.filterwarnings("ignore")
import logging
logging.getLogger("PIL").setLevel(logging.ERROR)

# ===================== CONFIG =====================
SRC_DIR = "Lable_Bouding.yolov8_merged/train"
DST_DIR = "yolo_dataset"
ZIP_OUT = "yolo_dataset_8class_20_04.zip"

VAL_RATIO = 0.15
TEST_RATIO = 0.15
SEED = 42

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
NC = len(CLASS_NAMES)

# Remap: class 8 (writing_marks trung) -> class 4
REMAP = {8: 4}

# Bbox filter - damage detection can bbox nho hon object detection thong thuong
MIN_BBOX_AREA = 0.0002   # 0.02% - giu duoc scratch/dirt nho (truoc la 0.0005)
MAX_BBOX_AREA = 0.90     # > 90% anh -> label sai (bao toan bo anh)

random.seed(SEED)


# ===================== LABEL CLEANING =====================
def clean_label(src_path):
    """Doc + remap + loc bbox. Tra ve (clean_lines, classes_in_img, stats)."""
    clean = []
    stats = Counter()
    classes = set()

    with open(src_path) as f:
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

            # Remap
            if cls_id in REMAP:
                cls_id = REMAP[cls_id]
                stats["remapped"] += 1

            if cls_id not in CLASS_NAMES:
                stats["unknown_cls"] += 1
                continue

            area = w * h
            if area < MIN_BBOX_AREA:
                stats["tiny"] += 1
                continue
            if area > MAX_BBOX_AREA:
                stats["huge"] += 1
                continue

            # Clamp [0,1] + dam bao kich thuoc > 0
            cx = max(0.0, min(1.0, cx))
            cy = max(0.0, min(1.0, cy))
            w = max(0.002, min(1.0, w))
            h = max(0.002, min(1.0, h))

            clean.append(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            classes.add(cls_id)

    return clean, classes, stats


# ===================== STRATIFIED SPLIT =====================
def stratified_3way_split(pairs, val_ratio, test_ratio):
    """
    Split theo 'anchor class' (class hiem nhat trong moi anh).
    Dam bao moi class xuat hien du trong train/val/test.
    """
    global_cnt = Counter()
    for _, _, cls_set in pairs:
        for c in cls_set:
            global_cnt[c] += 1

    # Bucket theo anchor class (hiem nhat trong anh)
    buckets = defaultdict(list)
    for i, (_, _, cls_set) in enumerate(pairs):
        if not cls_set:
            continue
        anchor = min(cls_set, key=lambda c: global_cnt[c])
        buckets[anchor].append(i)

    val_set, test_set = set(), set()
    for c, indices in buckets.items():
        random.shuffle(indices)
        n = len(indices)
        n_val = max(1, int(round(n * val_ratio)))
        n_test = max(1, int(round(n * test_ratio)))
        if n_val + n_test >= n:
            n_val = max(1, n // 3)
            n_test = max(1, n // 3)
        val_set.update(indices[:n_val])
        test_set.update(indices[n_val:n_val + n_test])

    train_set = set(range(len(pairs))) - val_set - test_set
    return train_set, val_set, test_set


# ===================== BALANCE (TRAIN ONLY) =====================
def flip_bbox(parts, mode):
    """Flip 1 bbox. mode: 'h' (horizontal), 'v' (vertical), 'hv' (ca 2)."""
    cls_id = parts[0]
    cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
    if "h" in mode:
        cx = 1.0 - cx
    if "v" in mode:
        cy = 1.0 - cy
    return f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def _load_file_ann_cnt(lbl_dir):
    """Doc tat ca label files. Tra ve dict stem -> Counter(class_id -> count)."""
    file_ann_cnt = {}
    for lf in os.listdir(lbl_dir):
        if not lf.endswith(".txt"):
            continue
        stem = os.path.splitext(lf)[0]
        cnt = Counter()
        with open(os.path.join(lbl_dir, lf)) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    try:
                        cnt[int(parts[0])] += 1
                    except ValueError:
                        continue
        if cnt:
            file_ann_cnt[stem] = cnt
    return file_ann_cnt


def balance_train(train_img_dir, train_lbl_dir):
    """
    Balance v2 - fix van de flip nhan ban class co-occurring:
      1. UNDERSAMPLE majority (> 1.3x target): xoa anh CHI chua majority classes
      2. SMART OVERSAMPLE minority: chon file co ty le target / (target + majority) cao
      3. RE-COUNT sau moi anh moi -> dung ngung khi du target

    Target = median annotations per class (tinh sau khi undersample).
    """
    from PIL import Image, ImageOps

    file_ann_cnt = _load_file_ann_cnt(train_lbl_dir)
    cls_cnt = Counter()
    for cnt in file_ann_cnt.values():
        cls_cnt.update(cnt)

    counts = sorted([cls_cnt.get(c, 0) for c in range(NC)])
    target = counts[len(counts) // 2]  # median
    UNDER_RATIO = 1.3   # xoa cho den khi majority <= 1.3x target

    print(f"  Initial counts: {dict(cls_cnt)}")
    print(f"  Target (median): {target}")

    # === STEP 1: UNDERSAMPLE majority ===
    majority = {c for c in range(NC) if cls_cnt[c] > target * UNDER_RATIO}
    removed = 0
    if majority:
        print(f"  Majority classes (>{target*UNDER_RATIO:.0f}): "
              f"{[CLASS_NAMES[c] for c in majority]}")

        # Ung vien: file CHI chua majority classes (khong dong hanh minority)
        pure_majority_files = [
            stem for stem, cnt in file_ann_cnt.items()
            if set(cnt.keys()).issubset(majority) and "_bal" not in stem
        ]
        # Uu tien xoa file nhieu majority nhat (giam nhanh nhat)
        pure_majority_files.sort(
            key=lambda s: -sum(file_ann_cnt[s][c] for c in majority)
        )

        for stem in pure_majority_files:
            # Stop neu moi majority da ve duoi nguong
            if all(cls_cnt[c] <= target * UNDER_RATIO for c in majority):
                break
            file_cnt = file_ann_cnt[stem]
            # Khong xoa neu lam bat ky majority nao rot duoi target (tranh over-shoot)
            if any(cls_cnt[c] - file_cnt[c] < target for c in majority if c in file_cnt):
                continue
            # Xoa file
            for c, n in file_cnt.items():
                cls_cnt[c] -= n
            for ext in (".jpg", ".jpeg", ".png"):
                p = os.path.join(train_img_dir, stem + ext)
                if os.path.exists(p):
                    os.remove(p)
                    break
            lp = os.path.join(train_lbl_dir, stem + ".txt")
            if os.path.exists(lp):
                os.remove(lp)
            del file_ann_cnt[stem]
            removed += 1

    print(f"  Undersampled: removed {removed} pure-majority images")
    print(f"  After undersample: {dict(cls_cnt)}")

    # === STEP 2: SMART OVERSAMPLE minority ===
    flip_modes = ["h", "v", "hv"]
    added_per_cls = Counter()

    # Xu ly tu class it nhat
    for cid in sorted(range(NC), key=lambda c: cls_cnt[c]):
        if cls_cnt[cid] >= target or cls_cnt[cid] == 0:
            continue

        # Ung vien: file co target class, uu tien:
        #   score = target_ann - 0.7 * majority_ann
        # File nhieu target class + it majority co score cao
        def score(stem):
            c = file_ann_cnt[stem]
            t = c[cid]
            m = sum(c[mc] for mc in majority) if majority else 0
            return t - 0.7 * m

        candidates = [s for s in file_ann_cnt if file_ann_cnt[s][cid] > 0
                      and "_bal" not in s]
        if not candidates:
            continue
        candidates.sort(key=score, reverse=True)

        # Round-robin qua top 60% candidates (tranh lap lai 1 file 10 lan)
        top_pool = candidates[:max(1, int(len(candidates) * 0.6))]
        random.shuffle(top_pool)

        i = 0
        flip_idx = 0
        max_iter = len(top_pool) * 3  # moi file toi da 3 flip modes
        safety = 0
        while cls_cnt[cid] < target and safety < max_iter:
            safety += 1
            stem = top_pool[i % len(top_pool)]
            mode = flip_modes[flip_idx % 3]
            i += 1
            if i % len(top_pool) == 0:
                flip_idx += 1

            img_src = None
            for ext in (".jpg", ".jpeg", ".png"):
                cand = os.path.join(train_img_dir, stem + ext)
                if os.path.exists(cand):
                    img_src = cand
                    break
            if not img_src:
                continue
            lbl_src = os.path.join(train_lbl_dir, stem + ".txt")
            if not os.path.exists(lbl_src):
                continue

            new_stem = f"{stem}_bal{cid}_{mode}"
            out_img = os.path.join(train_img_dir, new_stem + os.path.splitext(img_src)[1])
            if os.path.exists(out_img):
                continue  # da flip mode nay roi, skip

            try:
                with Image.open(img_src) as img:
                    img = img.convert("RGB")
                    if "h" in mode:
                        img = ImageOps.mirror(img)
                    if "v" in mode:
                        img = ImageOps.flip(img)
                    img.save(out_img, quality=92)
            except Exception:
                continue

            with open(lbl_src) as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            new_lines = [flip_bbox(ln.split(), mode) for ln in lines]
            with open(os.path.join(train_lbl_dir, new_stem + ".txt"), "w") as f:
                f.write("\n".join(new_lines))

            # Cap nhat counts: nhan day du co-occurring classes
            new_cnt = file_ann_cnt[stem].copy()
            file_ann_cnt[new_stem] = new_cnt
            cls_cnt.update(new_cnt)
            added_per_cls[cid] += 1

    total_added = sum(added_per_cls.values())
    print(f"  Oversampled: added {total_added} flipped images")
    print(f"  Final counts: {dict(cls_cnt)}")

    stats = {c: (cls_cnt[c], added_per_cls[c]) for c in range(NC)}
    return total_added, stats, target, removed


# ===================== FIX PNG =====================
def fix_png_profile(dst_dir):
    """Fix PNG iCCP profile + chuan hoa RGB. Xoa anh hong."""
    from PIL import Image, ImageFile
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    fixed = corrupted = total = 0
    for split in ("train", "val", "test"):
        img_dir = f"{dst_dir}/images/{split}"
        if not os.path.isdir(img_dir):
            continue
        for fn in os.listdir(img_dir):
            if not fn.lower().endswith(".png"):
                continue
            total += 1
            fp = os.path.join(img_dir, fn)
            try:
                with Image.open(fp) as img:
                    needs_fix = img.mode != "RGB" or "icc_profile" in img.info
                    if needs_fix:
                        img.convert("RGB").save(fp, "PNG", optimize=True)
                        fixed += 1
            except Exception:
                corrupted += 1
                lbl_fp = os.path.splitext(fp.replace(
                    os.sep + "images" + os.sep,
                    os.sep + "labels" + os.sep))[0] + ".txt"
                try:
                    os.remove(fp)
                    if os.path.exists(lbl_fp):
                        os.remove(lbl_fp)
                except OSError:
                    pass
    return total, fixed, corrupted


# ===================== STATISTICS =====================
def stats_split(img_dir, lbl_dir):
    """Dem anh + annotations theo class."""
    n_img = len([f for f in os.listdir(img_dir)
                 if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    cnt = Counter()
    for lf in os.listdir(lbl_dir):
        if not lf.endswith(".txt"):
            continue
        with open(os.path.join(lbl_dir, lf)) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    cnt[int(parts[0])] += 1
    return n_img, cnt


def print_split(name, n_img, cnt):
    tot = sum(cnt.values())
    print(f"\n  {name.upper()}: {n_img} images, {tot} annotations")
    for c in range(NC):
        v = cnt.get(c, 0)
        pct = v / tot * 100 if tot else 0
        print(f"    {c} {CLASS_NAMES[c]:17s}: {v:5d} ({pct:5.1f}%)")


# ===================== MAIN =====================
def main():
    src_img = os.path.join(SRC_DIR, "images")
    src_lbl = os.path.join(SRC_DIR, "labels")
    if not os.path.exists(src_img):
        print(f"ERROR: {src_img} khong ton tai!")
        sys.exit(1)

    print("=" * 70)
    print("PREPARE DAMAGE DETECTION DATASET (8 classes) - 1804")
    print("=" * 70)

    # === Step 1: Clean labels ===
    print(f"\n[1/6] Clean + remap labels...")
    img_files = sorted([f for f in os.listdir(src_img)
                        if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    pairs = []
    total_stats = Counter()
    skipped_empty = skipped_no_lbl = 0

    for img in img_files:
        stem = os.path.splitext(img)[0]
        lbl = os.path.join(src_lbl, stem + ".txt")
        if not os.path.exists(lbl):
            skipped_no_lbl += 1
            continue
        lines, classes, stats = clean_label(lbl)
        total_stats.update(stats)
        if not lines:
            skipped_empty += 1
            continue
        pairs.append((img, lines, classes))

    print(f"  Source images:           {len(img_files)}")
    print(f"  Valid images:            {len(pairs)}")
    print(f"  No label file:           {skipped_no_lbl}")
    print(f"  Empty after filter:      {skipped_empty}")
    print(f"  Class 8 -> 4 remap:      {total_stats.get('remapped', 0)}")
    print(f"  Bbox tiny (<{MIN_BBOX_AREA}): {total_stats.get('tiny', 0)}")
    print(f"  Bbox huge (>{MAX_BBOX_AREA}):  {total_stats.get('huge', 0)}")
    print(f"  Bad format:              {total_stats.get('bad_format', 0)}")

    # === Step 2: Stratified split ===
    print(f"\n[2/6] Stratified split {int((1-VAL_RATIO-TEST_RATIO)*100)}/"
          f"{int(VAL_RATIO*100)}/{int(TEST_RATIO*100)} (train/val/test)...")
    train_idx, val_idx, test_idx = stratified_3way_split(pairs, VAL_RATIO, TEST_RATIO)
    print(f"  Train: {len(train_idx)}  |  Val: {len(val_idx)}  |  Test: {len(test_idx)}")

    # === Step 3: Write dataset ===
    print(f"\n[3/6] Writing to {DST_DIR}/...")
    if os.path.exists(DST_DIR):
        shutil.rmtree(DST_DIR)
    for split in ("train", "val", "test"):
        os.makedirs(f"{DST_DIR}/images/{split}", exist_ok=True)
        os.makedirs(f"{DST_DIR}/labels/{split}", exist_ok=True)

    split_map = {}
    for i in train_idx: split_map[i] = "train"
    for i in val_idx:   split_map[i] = "val"
    for i in test_idx:  split_map[i] = "test"

    for i, (img, lines, _) in enumerate(pairs):
        split = split_map[i]
        stem = os.path.splitext(img)[0]
        shutil.copy2(os.path.join(src_img, img),
                     f"{DST_DIR}/images/{split}/{img}")
        with open(f"{DST_DIR}/labels/{split}/{stem}.txt", "w") as f:
            f.write("\n".join(lines))

    # Pre-balance stats
    print(f"\n  Pre-balance distribution:")
    for split in ("train", "val", "test"):
        n, c = stats_split(f"{DST_DIR}/images/{split}", f"{DST_DIR}/labels/{split}")
        print_split(split, n, c)

    # === Step 4: Balance TRAIN ===
    print(f"\n[4/6] Balance TRAIN set (undersample majority + smart oversample)...")
    added, bal_stats, target, removed = balance_train(
        f"{DST_DIR}/images/train", f"{DST_DIR}/labels/train"
    )
    print(f"  Target (median): {target}")
    print(f"  Images removed (undersample): {removed}")
    print(f"  Images added (oversample):    {added}")
    print(f"  Per class (final ann count / added copies):")
    for c in range(NC):
        final, add = bal_stats.get(c, (0, 0))
        if add > 0:
            marker = " <= oversampled"
        elif final < target:
            marker = " <= still below target"
        else:
            marker = ""
        print(f"    {c} {CLASS_NAMES[c]:17s}: {final:5d} (+{add:4d} copies){marker}")

    # === Step 5: Fix PNG profile ===
    print(f"\n[5/6] Fix PNG iCCP profile...")
    total, fixed, corrupted = fix_png_profile(DST_DIR)
    print(f"  Total PNG: {total}  |  Fixed: {fixed}  |  Corrupted removed: {corrupted}")

    # === Step 6: data.yaml + zip ===
    abs_path = os.path.abspath(DST_DIR).replace("\\", "/")
    yaml_lines = [
        f"path: {abs_path}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "",
        f"nc: {NC}",
        "names:",
    ]
    for cid in sorted(CLASS_NAMES):
        yaml_lines.append(f"  {cid}: {CLASS_NAMES[cid]}")
    yaml_txt = "\n".join(yaml_lines) + "\n"
    with open(f"{DST_DIR}/data.yaml", "w") as f:
        f.write(yaml_txt)
    with open("data.yaml", "w") as f:
        f.write(yaml_txt)

    print(f"\n[6/6] Zip thanh {ZIP_OUT}...")
    if os.path.exists(ZIP_OUT):
        os.remove(ZIP_OUT)
    with zipfile.ZipFile(ZIP_OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, _, files in os.walk(DST_DIR):
            for fn in files:
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, os.path.dirname(DST_DIR))
                zf.write(full, arc)
    size_mb = os.path.getsize(ZIP_OUT) / 1e6
    print(f"  Done! {ZIP_OUT} = {size_mb:.1f} MB")

    # === Final statistics ===
    print("\n" + "=" * 70)
    print("FINAL DATASET STATISTICS")
    print("=" * 70)
    grand = Counter()
    for split in ("train", "val", "test"):
        n, c = stats_split(f"{DST_DIR}/images/{split}", f"{DST_DIR}/labels/{split}")
        grand += c
        print_split(split, n, c)

    total_ann = sum(grand.values())
    print(f"\n  OVERALL: {total_ann} annotations")
    print(f"\n  Class distribution (after balance):")
    for c in range(NC):
        v = grand.get(c, 0)
        pct = v / total_ann * 100 if total_ann else 0
        bar = "#" * int(pct)
        print(f"    {c} {CLASS_NAMES[c]:17s}: {v:5d} ({pct:5.1f}%) {bar}")

    counts_list = [grand.get(c, 0) for c in range(NC) if grand.get(c, 0) > 0]
    ratio = max(counts_list) / min(counts_list) if counts_list else 0
    print(f"\n  Imbalance ratio (max/min): {ratio:.1f}x")
    if ratio < 2.5:
        print("  Balance TOT")
    elif ratio < 4:
        print("  Balance KHA")
    else:
        print("  Van con imbalance")
    print("=" * 70)

    print(f"\nDone! Dataset: {os.path.abspath(DST_DIR)}")
    print(f"Zip: {ZIP_OUT}")
    print(f"Upload len Kaggle Datasets slug: 'pbl5-dataset-1804-8class'")
    print(f"Roi chay notebook: pbl5_train_1804.ipynb")


if __name__ == "__main__":
    main()
