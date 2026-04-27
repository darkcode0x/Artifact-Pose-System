"""
Tao dataset 2-stage tu source goc (dataset_train_2704 + datatest).

Source:
  dataset_train_2704/train/{images,labels}/  - 2600 anh (mix HF + user)
  datatest/train/{images,labels}/             - 463 anh test (giu nguyen)

Pipeline:
  1. LOC HUG: bo file HF (filename '00xxx_png.rf...') trong train_2704
  2. BO PRE-AUGMENTED: bo suffix '_aug', '_bal'
  3. Resize anh ve max 1600px, JPEG quality 95
  4. Stratified 85/15 split train_2704 -> train/val
  5. Test giu nguyen tu datatest

Output:
  Stage 1 - YOLO binary detection:
    dataset_2stage/stage1/{images,labels}/{train,val,test}/
    + data.yaml (nc=1, names=[damage])
  Stage 2 - Classification (crop 256x256, padding 20%):
    dataset_2stage/stage2/{train,val,test}/<class>/<file>.jpg

Zip: data_26_04_2stage_<n_s1>_<n_s2crops>.zip

Chay: python preprocess_2stage.py
"""
import os
import re
import sys
import shutil
import zipfile
import warnings
import random
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
warnings.filterwarnings('ignore')

from PIL import Image

# ===================== CONFIG =====================
SRC_TV = Path('data/dataset_train_2704/train')
SRC_TS = Path('data/datatest/train')
DST = Path('data/dataset_2stage')
DST_S1 = DST / 'stage1'
DST_S2 = DST / 'stage2'

VAL_RATIO = 0.15
MIN_TEST_PER_CLASS = 25

# Image preprocessing
MAX_IMG_DIM = 1600
JPEG_QUALITY = 95

# Stage 2 crop config
STAGE2_PAD = 0.20            # padding xung quanh bbox
STAGE2_SIZE = 256            # crop output (training se 224 + crop)
STAGE2_MIN_PIXEL = 24        # bo bbox nho hon 24px (qua nho de classify)

SEED = 42
random.seed(SEED)

NC = 8
CLASS_NAMES = {
    0: 'material_loss', 1: 'peel', 2: 'scratch', 3: 'fold',
    4: 'writing_marks', 5: 'dirt', 6: 'staning', 7: 'burn_marks',
}

HF_REGEX = re.compile(r'^[0-9]+_(png|jpg|jpeg)\.rf\.', re.IGNORECASE)
AUG_REGEX = re.compile(r'(_aug\d+|_bal\d+_[hv]+)', re.IGNORECASE)
IMG_EXTS = ('.jpg', '.jpeg', '.png')


# ===================== HELPERS =====================
def is_hf(name): return bool(HF_REGEX.match(name))
def is_augmented(name): return bool(AUG_REGEX.search(name))


def parse_label(path: Path):
    """Parse YOLO label, validate. Tra ve list anns hop le."""
    if not path.exists():
        return [], ['missing']
    valid, invalid = [], []
    try:
        content = path.read_text(encoding='utf-8').strip()
    except Exception as e:
        return [], [f'read_error:{e}']
    if not content:
        return [], ['empty']
    for ln, line in enumerate(content.split('\n'), 1):
        parts = line.strip().split()
        if len(parts) != 5:
            invalid.append(f'L{ln}_malformed')
            continue
        try:
            cls = int(parts[0])
            cx, cy, w, h = map(float, parts[1:])
        except ValueError:
            invalid.append(f'L{ln}_parse')
            continue
        if not (0 <= cls < NC):
            invalid.append(f'L{ln}_class_oob')
            continue
        cx = max(0.0, min(1.0, cx))
        cy = max(0.0, min(1.0, cy))
        if w <= 0 or h <= 0 or w > 1 or h > 1:
            invalid.append(f'L{ln}_bbox_oob')
            continue
        if w * h < 1e-5 or w * h > 0.95:
            invalid.append(f'L{ln}_size_oob')
            continue
        valid.append((cls, cx, cy, w, h))
    return valid, invalid


def load_split(src_root: Path, label: str):
    """Load tat ca anh hop le, ap filter HF + aug."""
    img_dir = src_root / 'images'
    lbl_dir = src_root / 'labels'

    items = []
    n = Counter()
    for img_file in sorted(img_dir.iterdir()):
        if img_file.suffix.lower() not in IMG_EXTS:
            continue
        n['total'] += 1
        if is_hf(img_file.name):
            n['hf'] += 1
            continue
        if is_augmented(img_file.name):
            n['aug'] += 1
            continue
        anns, _ = parse_label(lbl_dir / f'{img_file.stem}.txt')
        if not anns:
            n['no_anns'] += 1
            continue
        items.append({
            'stem': img_file.stem,
            'img_path': img_file,
            'anns': anns,
            'classes': set(c for (c, *_) in anns),
        })
    print(f'  {label}: total={n["total"]} | HF_dropped={n["hf"]} | aug_dropped={n["aug"]} | '
          f'no_anns={n["no_anns"]} | KEEP={len(items)}')
    return items


def stratified_split(items, val_ratio=0.15, seed=42):
    rng = random.Random(seed)
    pool = list(items)
    rng.shuffle(pool)

    cls_count = Counter()
    for it in pool:
        for c in it['classes']:
            cls_count[c] += 1

    def primary_class(it):
        if not it['classes']:
            return -1
        return min(it['classes'], key=lambda c: cls_count[c])

    groups = defaultdict(list)
    for it in pool:
        groups[primary_class(it)].append(it)

    train, val = [], []
    for cls, group_items in groups.items():
        rng.shuffle(group_items)
        n_val = max(1, int(len(group_items) * val_ratio))
        val.extend(group_items[:n_val])
        train.extend(group_items[n_val:])
    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def fix_image_save(src: Path, dst_dir: Path, stem: str):
    """Resize ve max dim, JPG q95, fix iCCP. Tra ve path da save hoac None."""
    try:
        with Image.open(src) as im:
            im.load()
            if im.mode in ('P', 'RGBA', 'LA'):
                im = im.convert('RGB')
            elif im.mode != 'RGB':
                im = im.convert('RGB')
            w, h = im.size
            scale = min(1.0, MAX_IMG_DIM / max(w, h))
            if scale < 1.0:
                im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            dst = dst_dir / f'{stem}.jpg'
            im.save(dst, format='JPEG', quality=JPEG_QUALITY, optimize=True)
        return dst
    except Exception as e:
        print(f'  ! image_fail {src.name}: {e}')
        return None


def write_label_file(path: Path, anns):
    lines = [f'{c} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}' for (c, cx, cy, w, h) in anns]
    path.write_text('\n'.join(lines), encoding='utf-8')


def crop_with_padding(im: Image.Image, cx, cy, w, h, pad=0.20):
    W, H = im.size
    pad_w = w * W * pad
    pad_h = h * H * pad
    x1 = max(0, int((cx - w / 2) * W - pad_w))
    y1 = max(0, int((cy - h / 2) * H - pad_h))
    x2 = min(W, int((cx + w / 2) * W + pad_w))
    y2 = min(H, int((cy + h / 2) * H + pad_h))
    if x2 <= x1 or y2 <= y1:
        return None
    return im.crop((x1, y1, x2, y2))


def resize_pad_square(crop: Image.Image, size: int):
    crop.thumbnail((size, size), Image.LANCZOS)
    bg = Image.new('RGB', (size, size), (128, 128, 128))
    px = (size - crop.width) // 2
    py = (size - crop.height) // 2
    bg.paste(crop, (px, py))
    return bg


# ===================== MAIN =====================
def main():
    if not SRC_TV.exists():
        print(f'ERROR: {SRC_TV} khong ton tai')
        sys.exit(1)
    if not SRC_TS.exists():
        print(f'ERROR: {SRC_TS} khong ton tai')
        sys.exit(1)

    print('=' * 70)
    print('PREPROCESS 2-STAGE PIPELINE (26/04 - 27/04)')
    print('  Source: dataset_train_2704 (train+val) + datatest (463 test)')
    print('  Stage 1: YOLO binary detection')
    print('  Stage 2: Classification (8 class) tren crop')
    print('=' * 70)

    # ---- Step 1: Load + filter ----
    print('\n[1/6] Load & filter HF + pre-aug...')
    tv_items = load_split(SRC_TV, 'dataset_train_2704')
    ts_items = load_split(SRC_TS, 'datatest         ')

    # ---- Step 2: Test set check ----
    print('\n[2/6] Kiem tra test set...')
    ts_class = Counter()
    for it in ts_items:
        for c in it['classes']:
            ts_class[c] += 1
    print(f'  Test class image-counts:')
    for cid in range(NC):
        flag = ' <weak' if ts_class[cid] < MIN_TEST_PER_CLASS else ''
        print(f'    {cid} {CLASS_NAMES[cid]:15s}: {ts_class[cid]:4d}{flag}')

    weak = [c for c in range(NC) if ts_class[c] < MIN_TEST_PER_CLASS]
    if weak:
        print(f'  Class can bo sung: {[CLASS_NAMES[c] for c in weak]}')
        cands = defaultdict(list)
        for it in tv_items:
            for c in it['classes']:
                cands[c].append(it)
        rng = random.Random(SEED)
        for c in cands:
            rng.shuffle(cands[c])

        moved = set()
        for c in weak:
            need = MIN_TEST_PER_CLASS - ts_class[c]
            for cand in cands[c]:
                if need <= 0:
                    break
                if cand['stem'] in moved:
                    continue
                ts_items.append(cand)
                moved.add(cand['stem'])
                for cc in cand['classes']:
                    ts_class[cc] += 1
                need -= 1
        tv_items = [x for x in tv_items if x['stem'] not in moved]
        print(f'  -> Da chuyen {len(moved)} anh tu train_2704 sang test')
    else:
        print(f'  Test du class - khong can bo sung')

    # ---- Step 3: Stratified split ----
    print('\n[3/6] Stratified split train_2704 (85/15)...')
    train_items, val_items = stratified_split(tv_items, VAL_RATIO, SEED)
    print(f'  Train: {len(train_items)}')
    print(f'  Val:   {len(val_items)}')
    print(f'  Test:  {len(ts_items)}')

    # ---- Step 4: Tao folder + write Stage 1 ----
    print('\n[4/6] Ghi STAGE 1 (YOLO binary)...')
    if DST.exists():
        shutil.rmtree(DST)
    for split in ('train', 'val', 'test'):
        (DST_S1 / 'images' / split).mkdir(parents=True, exist_ok=True)
        (DST_S1 / 'labels' / split).mkdir(parents=True, exist_ok=True)
        for cname in CLASS_NAMES.values():
            (DST_S2 / split / cname).mkdir(parents=True, exist_ok=True)

    # cache resized images path -> Image (in mem) la nang. Thay vi do, save 1 lan vao stage1
    # roi crop tu file da save (size sat thuc)
    s1_count = Counter()
    s2_count = Counter()
    s2_per_class = {s: Counter() for s in ('train', 'val', 'test')}
    skipped_tiny = 0

    for split, items in (('train', train_items), ('val', val_items), ('test', ts_items)):
        for i, it in enumerate(items):
            # Save Stage 1 image (resized JPG q95)
            saved = fix_image_save(it['img_path'], DST_S1 / 'images' / split, it['stem'])
            if saved is None:
                continue

            # Stage 1 label: all class -> 0
            s1_lbl = DST_S1 / 'labels' / split / f"{it['stem']}.txt"
            s1_anns = [(0, cx, cy, w, h) for (_, cx, cy, w, h) in it['anns']]
            write_label_file(s1_lbl, s1_anns)
            s1_count[split] += 1

            # Stage 2 crops (read tu file da save de dung kich thuoc da resize)
            try:
                with Image.open(saved) as im:
                    if im.mode != 'RGB':
                        im = im.convert('RGB')
                    W, H = im.size
                    for idx, (cls, cx, cy, w, h) in enumerate(it['anns']):
                        if w * W < STAGE2_MIN_PIXEL or h * H < STAGE2_MIN_PIXEL:
                            skipped_tiny += 1
                            continue
                        crop = crop_with_padding(im, cx, cy, w, h, pad=STAGE2_PAD)
                        if crop is None:
                            continue
                        crop = resize_pad_square(crop, STAGE2_SIZE)
                        cname = CLASS_NAMES[cls]
                        out = DST_S2 / split / cname / f"{it['stem']}_{idx:03d}.jpg"
                        crop.save(out, format='JPEG', quality=JPEG_QUALITY, optimize=True)
                        s2_count[split] += 1
                        s2_per_class[split][cname] += 1
            except Exception as e:
                print(f'  ! crop_fail {it["stem"]}: {e}')

            if (i + 1) % 200 == 0:
                print(f'    {split} {i+1}/{len(items)}  s1={s1_count[split]}  s2={s2_count[split]}')
        print(f'  {split:5s}: stage1={s1_count[split]}  stage2_crops={s2_count[split]}')

    # ---- Step 5: yaml + summary ----
    print('\n[5/6] Tao data.yaml + thong ke...')
    yaml_text = (
        f'path: {DST_S1.resolve().as_posix()}\n'
        f'train: images/train\n'
        f'val: images/val\n'
        f'test: images/test\n\n'
        f'nc: 1\n'
        f'names:\n'
        f'  0: damage\n'
    )
    (DST_S1 / 'data.yaml').write_text(yaml_text, encoding='utf-8')

    print(f'\n  STAGE 1 (YOLO binary):')
    print(f'    {"split":<10} {"images":>8}')
    for s in ('train', 'val', 'test'):
        print(f'    {s:<10} {s1_count[s]:>8}')

    print(f'\n  STAGE 2 (classification crops):')
    print(f'    Skipped tiny bbox (<{STAGE2_MIN_PIXEL}px): {skipped_tiny}')
    print(f'    {"class":<17} {"train":>8} {"val":>8} {"test":>8}')
    print(f'    {"-"*17} {"-"*8} {"-"*8} {"-"*8}')
    for cname in CLASS_NAMES.values():
        print(f'    {cname:<17} '
              f'{s2_per_class["train"][cname]:>8} '
              f'{s2_per_class["val"][cname]:>8} '
              f'{s2_per_class["test"][cname]:>8}')
    tot = {s: sum(s2_per_class[s].values()) for s in ('train', 'val', 'test')}
    print(f'    {"TOTAL":<17} {tot["train"]:>8} {tot["val"]:>8} {tot["test"]:>8}')

    # ---- Step 6: Zip ----
    n_s1 = sum(s1_count.values())
    n_s2 = sum(s2_count.values())
    zip_name = f'data_26_04_2stage_{n_s1}_{n_s2}.zip'
    print(f'\n[6/6] Zip -> {zip_name}...')
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, _, files in os.walk(DST):
            for f in files:
                full = Path(root) / f
                zf.write(full, full.relative_to(DST.parent))
    size_mb = Path(zip_name).stat().st_size / 1e6
    print(f'  {zip_name}: {size_mb:.1f} MB')

    print('\n' + '=' * 70)
    print('DONE')
    print(f'  dataset_2stage/stage1/  -> {n_s1} images (binary detection)')
    print(f'  dataset_2stage/stage2/  -> {n_s2} crops (8-class classification)')
    print(f'  Train+Val: {len(train_items) + len(val_items)}  Test: {len(ts_items)}')
    print(f'  Zip: {zip_name}')
    print('=' * 70)


if __name__ == '__main__':
    main()
