"""Load the trained YOLO model and run live detection from the webcam.

Usage:
    python test_webcam.py
    python test_webcam.py --weights best-121304-8643pt.pt --source 0 --conf 0.25 --imgsz 960
Press `q` to quit, `s` to save a snapshot of the current annotated frame.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
from ultralytics import YOLO


HERE = Path(__file__).resolve().parent
DEFAULT_WEIGHTS = HERE / "best-121304-8643pt.pt"
SNAPSHOT_DIR = HERE / "snapshots"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Webcam test for trained YOLO model")
    parser.add_argument("--weights", type=str, default=str(DEFAULT_WEIGHTS),
                        help="Path to .pt weights file")
    parser.add_argument("--source", type=str, default="0",
                        help="Camera index (e.g. 0, 1) or video file path")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=0.5, help="IoU threshold for NMS")
    parser.add_argument("--imgsz", type=int, default=960, help="Inference image size")
    parser.add_argument("--device", type=str, default="",
                        help="Device: '' (auto), 'cpu', '0' for GPU 0")
    parser.add_argument("--width", type=int, default=1920, help="Requested capture width")
    parser.add_argument("--height", type=int, default=1080, help="Requested capture height")
    parser.add_argument("--fps", type=int, default=30, help="Requested capture FPS")
    parser.add_argument("--fourcc", type=str, default="MJPG",
                        help="FourCC codec (MJPG recommended for HD@30)")
    parser.add_argument("--autofocus", type=int, default=1, help="1=on, 0=off")
    parser.add_argument("--focus", type=float, default=-1.0,
                        help="Manual focus (0-255, -1 to skip). Requires --autofocus 0")
    parser.add_argument("--sharpen", action="store_true",
                        help="Apply unsharp-mask to each frame before inference")
    return parser.parse_args()


def resolve_source(source: str) -> int | str:
    return int(source) if source.isdigit() else source


def open_capture(
    source: int | str,
    width: int,
    height: int,
    fps: int,
    fourcc: str,
    autofocus: int,
    focus: float,
) -> cv2.VideoCapture:
    if isinstance(source, int):
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(source)
    else:
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        raise RuntimeError(f"Can not open video source: {source}")

    if fourcc:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, autofocus)
    if autofocus == 0 and focus >= 0:
        cap.set(cv2.CAP_PROP_FOCUS, focus)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"[info] Capture: {actual_w}x{actual_h} @ {actual_fps:.1f} FPS, fourcc={fourcc}")
    return cap


def unsharp_mask(image, sigma: float = 1.0, amount: float = 1.2):
    blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=sigma, sigmaY=sigma)
    return cv2.addWeighted(image, 1 + amount, blurred, -amount, 0)


def main() -> None:
    args = parse_args()

    weights_path = Path(args.weights)
    if not weights_path.is_absolute():
        weights_path = (HERE / weights_path).resolve()
    if not weights_path.exists():
        raise FileNotFoundError(f"Weights file not found: {weights_path}")

    print(f"[info] Loading model: {weights_path}")
    model = YOLO(str(weights_path))
    print(f"[info] Classes ({len(model.names)}): {model.names}")

    source = resolve_source(args.source)
    cap = open_capture(
        source, args.width, args.height, args.fps, args.fourcc,
        args.autofocus, args.focus,
    )
    print(f"[info] Opened source {source}. Press 'q' to quit, 's' snapshot, "
          f"'+/-' focus, 'a' toggle autofocus, 'u' toggle unsharp.")
    apply_unsharp = args.sharpen
    autofocus_on = bool(args.autofocus)
    manual_focus = args.focus if args.focus >= 0 else 0.0

    window_name = "YOLO Webcam Test"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    prev_t = time.time()
    fps_smooth = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("[warn] Failed to read frame. Stopping.")
                break

            infer_frame = unsharp_mask(frame) if apply_unsharp else frame

            results = model.predict(
                infer_frame,
                imgsz=args.imgsz,
                conf=args.conf,
                iou=args.iou,
                device=args.device or None,
                verbose=False,
            )
            annotated = results[0].plot()

            now = time.time()
            dt = now - prev_t
            prev_t = now
            if dt > 0:
                fps = 1.0 / dt
                fps_smooth = fps if fps_smooth == 0 else 0.9 * fps_smooth + 0.1 * fps

            n_det = len(results[0].boxes) if results[0].boxes is not None else 0
            af_label = "AF" if autofocus_on else f"MF={manual_focus:.0f}"
            sharp_label = "sharp" if apply_unsharp else "raw"
            overlay = (f"FPS: {fps_smooth:5.1f}  det: {n_det}  "
                       f"conf>={args.conf}  {af_label}  {sharp_label}")
            cv2.putText(annotated, overlay, (10, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

            cv2.imshow(window_name, annotated)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                break
            if key == ord("s"):
                SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
                out_path = SNAPSHOT_DIR / f"snap_{int(now)}.jpg"
                cv2.imwrite(str(out_path), annotated)
                print(f"[info] Saved snapshot: {out_path}")
            elif key == ord("u"):
                apply_unsharp = not apply_unsharp
                print(f"[info] Unsharp mask: {apply_unsharp}")
            elif key == ord("a"):
                autofocus_on = not autofocus_on
                cap.set(cv2.CAP_PROP_AUTOFOCUS, 1 if autofocus_on else 0)
                print(f"[info] Autofocus: {autofocus_on}")
            elif key in (ord("+"), ord("=")) and not autofocus_on:
                manual_focus = min(255.0, manual_focus + 5.0)
                cap.set(cv2.CAP_PROP_FOCUS, manual_focus)
                print(f"[info] Focus: {manual_focus:.0f}")
            elif key in (ord("-"), ord("_")) and not autofocus_on:
                manual_focus = max(0.0, manual_focus - 5.0)
                cap.set(cv2.CAP_PROP_FOCUS, manual_focus)
                print(f"[info] Focus: {manual_focus:.0f}")
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
