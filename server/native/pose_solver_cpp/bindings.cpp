#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <pybind11/eigen.h>
#include "quadtree.h"
#include "hybrid_pose_solver.h"
#include "stereo_triangulation.h"
#include "orb_matcher.h"
#include "deviation_calculator.h"

namespace py = pybind11;
using namespace cv;
using namespace std;
using namespace Eigen;

// Helper: numpy array -> cv::Mat
static Mat numpyToMat(py::array_t<uint8_t> input) {
    py::buffer_info buf = input.request();
    Mat image;
    if (buf.ndim == 2) {
        image = Mat(buf.shape[0], buf.shape[1], CV_8UC1, (uint8_t*)buf.ptr).clone();
    } else if (buf.ndim == 3 && buf.shape[2] == 3) {
        image = Mat(buf.shape[0], buf.shape[1], CV_8UC3, (uint8_t*)buf.ptr).clone();
    } else {
        throw runtime_error("Unsupported image format. Expected (H, W) or (H, W, 3)");
    }
    return image;
}

// Helper: parse camera K, D from numpy
static void parseCameraParams(py::array_t<double> camMatrix, py::array_t<double> distCoeffs,
                               Mat& K, Mat& D) {
    py::buffer_info kBuf = camMatrix.request();
    K = Mat(3, 3, CV_64F, (double*)kBuf.ptr).clone();

    py::buffer_info dBuf = distCoeffs.request();
    int rows = dBuf.shape.size() == 2 ? dBuf.shape[0] : 1;
    int cols = dBuf.shape.size() == 2 ? dBuf.shape[1] : dBuf.shape[0];
    D = Mat(rows, cols, CV_64F, (double*)dBuf.ptr).clone();
}

// MODULE: QuadTree ORB Extraction

py::dict extractWithQuadTreeFromNumpy(
    py::array_t<uint8_t> input,
    int maxInitialFeatures,
    int minNodeSize,
    int maxDepth
) {
    Mat image = numpyToMat(input);
    QuadTreeResult qr = extractWithQuadTree(image, maxInitialFeatures, minNodeSize, maxDepth);

    py::list kpList;
    for (const auto& kp : qr.keypoints) {
        py::dict point;
        point["x"] = kp.pt.x;
        point["y"] = kp.pt.y;
        point["size"] = kp.size;
        point["angle"] = kp.angle;
        point["response"] = kp.response;
        kpList.append(point);
    }

    py::array_t<uint8_t> descArray;
    if (!qr.descriptors.empty()) {
        vector<ssize_t> shape = {qr.descriptors.rows, qr.descriptors.cols};
        vector<ssize_t> strides = {(ssize_t)(qr.descriptors.cols * sizeof(uint8_t)), (ssize_t)sizeof(uint8_t)};
        descArray = py::array_t<uint8_t>(shape, strides, qr.descriptors.data);
    }

    py::list gridList;
    for (const auto& cell : qr.gridCells) {
        py::dict rect;
        rect["x"] = cell.x;
        rect["y"] = cell.y;
        rect["w"] = cell.width;
        rect["h"] = cell.height;
        gridList.append(rect);
    }

    py::dict output;
    output["keypoints"] = kpList;
    output["descriptors"] = descArray;
    output["grid_cells"] = gridList;
    output["total_detected"] = qr.totalDetected;
    output["total_after_quadtree"] = (int)qr.keypoints.size();
    return output;
}


// MODULE: Hybrid Pose Solver (Diamond high-weight + ORB Huber)

py::dict hybridOptimizeFromNumpy(
    py::array_t<double> initialRvec,
    py::array_t<double> initialTvec,
    py::array_t<double> diamond3d,
    py::array_t<double> diamond2d,
    py::array_t<double> orb3d,
    py::array_t<double> orb2d,
    py::array_t<double> camMatrix,
    py::array_t<double> distCoeffs,
    double diamondWeight,
    double orbWeight,
    double huberDelta,
    int maxIterations
) {
    Mat K, D;
    parseCameraParams(camMatrix, distCoeffs, K, D);

    auto rv = initialRvec.unchecked<1>();
    auto tv = initialTvec.unchecked<1>();
    Vec3d rvec(rv(0), rv(1), rv(2));
    Vec3d tvec(tv(0), tv(1), tv(2));

    // Diamond observations
    vector<DiamondObservation> diamondObs;
    auto d3d = diamond3d.unchecked<2>();
    auto d2d = diamond2d.unchecked<2>();
    for (ssize_t i = 0; i < d3d.shape(0); i++) {
        DiamondObservation obs;
        obs.point3d = Vector3d(d3d(i, 0), d3d(i, 1), d3d(i, 2));
        obs.point2d = Vector2d(d2d(i, 0), d2d(i, 1));
        diamondObs.push_back(obs);
    }

    // ORB observations
    vector<ORBObservation> orbObs;
    auto o3d = orb3d.unchecked<2>();
    auto o2d = orb2d.unchecked<2>();
    for (ssize_t i = 0; i < o3d.shape(0); i++) {
        ORBObservation obs;
        obs.point3d = Vector3d(o3d(i, 0), o3d(i, 1), o3d(i, 2));
        obs.point2d = Vector2d(o2d(i, 0), o2d(i, 1));
        orbObs.push_back(obs);
    }

    HybridPoseSolver solver;
    solver.setCameraParams(K, D);

    HybridConfig config;
    config.diamondWeight = diamondWeight;
    config.orbWeight = orbWeight;
    config.huberDelta = huberDelta;
    config.maxIterations = maxIterations;
    config.verbose = false;
    solver.setConfig(config);

    HybridPoseResult res = solver.optimize(rvec, tvec, diamondObs, orbObs);

    py::dict result;
    result["rvec"] = py::make_tuple(res.rvec[0], res.rvec[1], res.rvec[2]);
    result["tvec"] = py::make_tuple(res.tvec[0], res.tvec[1], res.tvec[2]);
    result["initial_chi2"] = res.initialChi2;
    result["final_chi2"] = res.finalChi2;
    result["diamond_error"] = res.diamondError;
    result["orb_mean_error"] = res.orbMeanError;
    result["num_orb_inliers"] = res.numOrbInliers;
    result["num_orb_outliers"] = res.numOrbOutliers;
    result["iterations"] = res.iterations;
    result["converged"] = res.converged;
    return result;
}

// MODULE: Stereo Triangulation

py::dict triangulateFromNumpy(
    py::array_t<double> ptsLeft,
    py::array_t<double> ptsRight,
    py::array_t<double> camMatrix,
    py::array_t<double> distCoeffs,
    double baseline
) {
    Mat K, D;
    parseCameraParams(camMatrix, distCoeffs, K, D);

    auto left = ptsLeft.unchecked<2>();
    auto right = ptsRight.unchecked<2>();

    vector<Point2f> vLeft, vRight;
    for (ssize_t i = 0; i < left.shape(0); i++) {
        vLeft.push_back(Point2f(left(i, 0), left(i, 1)));
        vRight.push_back(Point2f(right(i, 0), right(i, 1)));
    }

    StereoTriangulator triangulator;
    triangulator.setCameraParams(K, D);

    StereoConfig cfg;
    cfg.baseline = baseline;
    triangulator.setConfig(cfg);

    StereoTriangulationResult res = triangulator.triangulate(vLeft, vRight);

    ssize_t n = res.points.size();
    py::array_t<double> pts3dArray({n, (ssize_t)3});
    auto buf = pts3dArray.mutable_unchecked<2>();
    py::list validList;
    for (ssize_t i = 0; i < n; i++) {
        buf(i, 0) = res.points[i].point3d.x();
        buf(i, 1) = res.points[i].point3d.y();
        buf(i, 2) = res.points[i].point3d.z();
        validList.append(res.points[i].valid);
    }

    py::dict result;
    result["points_3d"] = pts3dArray;
    result["valid_mask"] = validList;
    result["num_valid"] = res.numValid;
    result["num_rejected"] = res.numRejected;
    result["mean_depth"] = res.meanDepth;
    result["mean_reproj_error"] = res.meanReprojError;
    return result;
}

// MODULE: ORB Matcher
py::dict matchStereoFromNumpy(
    py::array_t<uint8_t> descLeft,
    py::array_t<uint8_t> descRight,
    float ratioThreshold,
    int maxHammingDistance
) {
    py::buffer_info bL = descLeft.request();
    py::buffer_info bR = descRight.request();

    Mat dL(bL.shape[0], bL.shape[1], CV_8UC1, (uint8_t*)bL.ptr);
    Mat dR(bR.shape[0], bR.shape[1], CV_8UC1, (uint8_t*)bR.ptr);

    ORBMatcher matcher;
    MatchConfig cfg;
    cfg.ratioThreshold = ratioThreshold;
    cfg.maxHammingDistance = maxHammingDistance;
    matcher.setConfig(cfg);

    vector<DMatch> matches = matcher.matchBruteForce(dL, dR);

    py::list matchList;
    for (const auto& m : matches) {
        py::dict md;
        md["query_idx"] = m.queryIdx;
        md["train_idx"] = m.trainIdx;
        md["distance"] = m.distance;
        matchList.append(md);
    }

    py::dict result;
    result["matches"] = matchList;
    result["num_matches"] = (int)matches.size();
    return result;
}

py::dict matchWith3DRefFromNumpy(
    py::array_t<double> currentKeypoints,
    py::array_t<uint8_t> currentDescriptors,
    py::array_t<double> refPoints3d,
    py::array_t<uint8_t> refDescriptors,
    float ratioThreshold,
    int maxHammingDistance
) {
    auto kpBuf = currentKeypoints.unchecked<2>();
    py::buffer_info cdBuf = currentDescriptors.request();
    auto ref3dBuf = refPoints3d.unchecked<2>();
    py::buffer_info rdBuf = refDescriptors.request();

    vector<KeyPoint> kps;
    for (ssize_t i = 0; i < kpBuf.shape(0); i++) {
        kps.push_back(KeyPoint(Point2f(kpBuf(i, 0), kpBuf(i, 1)), 31.0f));
    }

    Mat cDesc(cdBuf.shape[0], cdBuf.shape[1], CV_8UC1, (uint8_t*)cdBuf.ptr);
    Mat rDesc(rdBuf.shape[0], rdBuf.shape[1], CV_8UC1, (uint8_t*)rdBuf.ptr);

    vector<Vector3d> ref3d;
    for (ssize_t i = 0; i < ref3dBuf.shape(0); i++) {
        ref3d.push_back(Vector3d(ref3dBuf(i, 0), ref3dBuf(i, 1), ref3dBuf(i, 2)));
    }

    ORBMatcher matcher;
    MatchConfig cfg;
    cfg.ratioThreshold = ratioThreshold;
    cfg.maxHammingDistance = maxHammingDistance;
    matcher.setConfig(cfg);

    Match3D2DResult res = matcher.matchWith3DReference(kps, cDesc, ref3d, rDesc);

    ssize_t n = res.matches.size();
    py::array_t<double> pts3d({n, (ssize_t)3});
    py::array_t<double> pts2d({n, (ssize_t)2});
    auto b3d = pts3d.mutable_unchecked<2>();
    auto b2d = pts2d.mutable_unchecked<2>();

    for (ssize_t i = 0; i < n; i++) {
        b3d(i, 0) = res.matches[i].point3d.x();
        b3d(i, 1) = res.matches[i].point3d.y();
        b3d(i, 2) = res.matches[i].point3d.z();
        b2d(i, 0) = res.matches[i].point2d.x();
        b2d(i, 1) = res.matches[i].point2d.y();
    }

    py::dict result;
    result["points_3d"] = pts3d;
    result["points_2d"] = pts2d;
    result["num_matches"] = res.numMatches;
    result["mean_distance"] = res.meanDistance;
    return result;
}


// PYBIND11 MODULE DEFINITION

PYBIND11_MODULE(pose_solver_cpp, m) {
    m.doc() = "Artifact Pose System - C++ Core Module";

    // --- QuadTree ORB ---
    m.def("extract_with_quadtree", &extractWithQuadTreeFromNumpy,
          py::arg("image"),
          py::arg("max_initial_features") = 5000,
          py::arg("min_node_size") = 64,
          py::arg("max_depth") = 7,
          "Extract ORB features with QuadTree distribution"
    );

    // --- Hybrid Pose Solver (Diamond + ORB weighted G2O) ---
    m.def("hybrid_optimize", &hybridOptimizeFromNumpy,
          py::arg("initial_rvec"),
          py::arg("initial_tvec"),
          py::arg("diamond_3d"),
          py::arg("diamond_2d"),
          py::arg("orb_3d"),
          py::arg("orb_2d"),
          py::arg("camera_matrix"),
          py::arg("dist_coeffs"),
          py::arg("diamond_weight") = 10000.0,
          py::arg("orb_weight") = 1.0,
          py::arg("huber_delta") = 2.0,
          py::arg("max_iterations") = 20,
          "Hybrid G2O: Diamond (high weight) + ORB (Huber kernel)"
    );

    // --- Module: Stereo Triangulation ---
    m.def("triangulate_stereo", &triangulateFromNumpy,
          py::arg("points_left"),
          py::arg("points_right"),
          py::arg("camera_matrix"),
          py::arg("dist_coeffs"),
          py::arg("baseline") = 0.10,
          "Stereo triangulation with quality filtering"
    );

    // --- Module: ORB Matcher ---
    m.def("match_stereo", &matchStereoFromNumpy,
          py::arg("desc_left"),
          py::arg("desc_right"),
          py::arg("ratio_threshold") = 0.75f,
          py::arg("max_hamming_distance") = 64,
          "Match ORB descriptors with Lowe's ratio test"
    );
    m.def("match_with_3d_reference", &matchWith3DRefFromNumpy,
          py::arg("current_keypoints"),
          py::arg("current_descriptors"),
          py::arg("ref_points_3d"),
          py::arg("ref_descriptors"),
          py::arg("ratio_threshold") = 0.75f,
          py::arg("max_hamming_distance") = 64,
          "Match current ORB with 3D reference for pose estimation"
    );

    // --- Module: Deviation Calculator + Motor Command ---
    m.def("calculate_deviation", [](
        py::list rvecGolden, py::list tvecGolden,
        py::list rvecCurrent, py::list tvecCurrent,
        double transTolerance, double rotTolerance,
        double servoMinDeg, bool sequentialMode, double stepsPerMm
    ) {
        Vec3d rg(rvecGolden[0].cast<double>(), rvecGolden[1].cast<double>(), rvecGolden[2].cast<double>());
        Vec3d tg(tvecGolden[0].cast<double>(), tvecGolden[1].cast<double>(), tvecGolden[2].cast<double>());
        Vec3d rc(rvecCurrent[0].cast<double>(), rvecCurrent[1].cast<double>(), rvecCurrent[2].cast<double>());
        Vec3d tc(tvecCurrent[0].cast<double>(), tvecCurrent[1].cast<double>(), tvecCurrent[2].cast<double>());

        DeviationConfig dcfg;
        dcfg.transTolerance  = transTolerance;
        dcfg.rotTolerance    = rotTolerance;
        dcfg.servoMinDeg     = servoMinDeg;
        dcfg.sequentialMode  = sequentialMode;
        dcfg.stepsPerMm      = stepsPerMm;

        DeviationCalculator calc;
        calc.setConfig(dcfg);
        PoseDeviation dev = calc.calculate(rg, tg, rc, tc);
        MotorCommand cmd = deviationToMotorCommand(dev, stepsPerMm, servoMinDeg, sequentialMode);

        py::dict result;
        result["delta_x"]               = dev.deltaX;
        result["delta_y"]               = dev.deltaY;
        result["delta_z"]               = dev.deltaZ;
        result["delta_pan"]             = dev.deltaPan;
        result["delta_tilt"]            = dev.deltaTilt;
        result["delta_roll"]            = dev.deltaRoll;
        result["translation_mag"]       = dev.translationMag;
        result["rotation_mag"]          = dev.rotationMag;
        result["within_tolerance"]      = dev.withinTolerance;
        result["within_trans_tolerance"]= dev.withinTransTolerance;  // new: separate status
        result["within_rot_tolerance"]  = dev.withinRotTolerance;    // new: separate status

        py::dict motorDict;
        motorDict["move_x"]       = cmd.moveX;
        motorDict["move_z"]       = cmd.moveZ;
        motorDict["rotate_pan"]   = cmd.rotatePan;   // already rounded/zeroed
        motorDict["rotate_tilt"]  = cmd.rotateTilt;  // already rounded/zeroed
        motorDict["priority"]     = cmd.priority;
        result["motor_command"] = motorDict;

        return result;
    },
    py::arg("rvec_golden"), py::arg("tvec_golden"),
    py::arg("rvec_current"), py::arg("tvec_current"),
    py::arg("trans_tolerance")  = 0.010,   // 10mm
    py::arg("rot_tolerance")    = 1.0,     // 1.0 degree (== servo min step)
    py::arg("servo_min_deg")    = 1.0,     // Servo hardware minimum step
    py::arg("sequential_mode")  = true,    // Translation-first priority
    py::arg("steps_per_mm")     = 860.0,   // Stepper motor steps/mm
    "Calculate pose deviation and motor command.\n"
    "Rotation commands are rounded to nearest servo_min_deg step;\n"
    "angles in the dead zone (< 0.5*servo_min_deg) are zeroed.\n"
    "When sequential_mode=True and both trans+rot are needed,\n"
    "only translation is sent; rotation is deferred to the next iteration."
    );
}
