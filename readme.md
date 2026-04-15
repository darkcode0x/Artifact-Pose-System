# Artifact Pose System

6-DoF pose estimation and correction using **Diamond ArUco markers** + **ORB features** + **G2O graph optimization** with asymmetric weighting.

See [Introduction.md](Introduction.md) for detailed architecture, pipeline, and Hybrid G2O strategy documentation.

---

## Quick Start

### 1. Install Dependencies

```bash
sudo apt install -y build-essential cmake libopencv-dev python3-opencv \
    libeigen3-dev pybind11-dev python3-dev python3-pip
pip3 install numpy
```

### 2. Build

```bash
# Build G2O (once)
cd libs && ./build_g2o.sh && cd ..

# Build C++ module
cd cpp_core && mkdir -p build && cd build && cmake .. && make -j4 && cd ../..

# Or use the convenience script:
./build_all.sh
```

### 3. Calibrate Camera (if needed)

```bash
# Capture 20-30 images of ChArUco board A2, then:
cd python_core
python3 calibrate_camera.py --images ../Calibration/images
```

### 4. Initialize Golden Pose

```bash
cd python_core
python3 initialize_golden.py \
  --left ../data/capture_4kleft.png \
  --right ../data/capture_4kright.png \
  --visual
```

### 5. Run Correction

```bash
python3 correction_loop.py --image ../data/current.png
# Add --visual for visualization output in data/visualization/
python3 correction_loop.py --image ../data/current.png --visual
```

---

## Project Structure

```
Artifact-Pose-System/
├── cpp_core/                     # C++ core (5 modules → pybind11)
│   ├── bindings.cpp              # 6 Python-callable functions
│   ├── CMakeLists.txt
│   ├── include/                  # 5 headers
│   │   ├── quadtree.h
│   │   ├── hybrid_pose_solver.h
│   │   ├── stereo_triangulation.h
│   │   ├── orb_matcher.h
│   │   └── deviation_calculator.h
│   └── src/                      # 5 implementations
│       ├── quadtree.cpp
│       ├── hybrid_pose_solver.cpp
│       ├── stereo_triangulation.cpp
│       ├── orb_matcher.cpp
│       └── deviation_calculator.cpp
├── python_core/
│   ├── common.py                 # Shared utilities
│   ├── initialize_golden.py      # Pipeline A: Golden pose setup
│   ├── correction_loop.py        # Pipeline B: Correction loop
│   ├── calibrate_camera.py       # Camera calibration
│   ├── camera_capture.py         # Raspberry Pi capture
│   └── pose_visualization.ipynb  # Visualization notebook
├── Calibration/
│   ├── camera_params_4k.yaml     # Camera intrinsics
│   └── images/                   # Calibration images
├── data/                         # Golden pose + test images
├── libs/g2o/                     # G2O optimization library
├── Introduction.md               # Detailed documentation
└── README.md
```

---

## Pipeline

**Pipeline A — Initialize** (once):
Diamond detect → ORB stereo extract → Stereo match → Triangulate 3D → Save golden pose

**Pipeline B — Correct** (each frame):
1. Diamond detect → initial pose + 4 anchor observations
2. ORB + QuadTree → feature extraction
3. Match ORB with golden 3D reference → N 3D-2D pairs
4. **Hybrid G2O**: Diamond (weight 10⁴) + ORB (weight 1, Huber δ=2px)
5. Deviation → motor command

---

## C++ Binding Functions

```python
import pose_solver_cpp as cpp

# QuadTree ORB extraction
cpp.extract_with_quadtree(image, max_initial_features=5000, min_node_size=64, max_depth=7)

# Stereo matching (BF Hamming + Lowe's ratio test)
cpp.match_stereo(desc_left, desc_right, ratio_threshold=0.75, max_hamming_distance=64)

# Stereo triangulation (DLT + quality filtering)
cpp.triangulate_stereo(pts_left, pts_right, K, D, baseline=0.10)

# Match current ORB with 3D reference
cpp.match_with_3d_reference(kp_xy, desc_curr, ref_3d, ref_desc)

# Hybrid G2O optimization (Diamond 10⁴ + ORB 1 + Huber)
cpp.hybrid_optimize(rvec, tvec, diamond_3d, diamond_2d, orb_3d, orb_2d, K, D)

# 6-DoF deviation + motor command
cpp.calculate_deviation(rvec_gold, tvec_gold, rvec_curr, tvec_curr, trans_tol, rot_tol)
```

---

## Requirements

- OpenCV 4.7+ (with ArUco/objdetect)
- Eigen3, G2O, pybind11
- Python 3.8+, NumPy
- Picamera2 (for Raspberry Pi capture only)

## Troubleshooting

| Error | Fix |
|-------|-----|
| `libg2o_core.so not found` | `cd libs && ./build_g2o.sh && sudo ldconfig` |
| `No module named pose_solver_cpp` | Run `./build_all.sh` or copy `.so` from `cpp_core/build/` to `python_core/` |
| `OpenCV not found` | `sudo apt install libopencv-dev` |
| CMake link errors | `cd cpp_core/build && rm -rf * && cmake .. && make -j4` |

---

## Author

ThePiece

## Acknowledgments

- G2O — graph optimization library
- OpenCV — computer vision
- pybind11 — C++/Python bridge
