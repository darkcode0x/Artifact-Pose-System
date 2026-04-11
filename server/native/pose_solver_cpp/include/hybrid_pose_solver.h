#ifndef HYBRID_POSE_SOLVER_H
#define HYBRID_POSE_SOLVER_H

#include <opencv2/opencv.hpp>
#include <Eigen/Core>
#include <Eigen/Geometry>
#include <vector>

// ============================================================
// Observation types for Hybrid optimization
// ============================================================

// Diamond Marker observation (4 chessboard corners)
// High weight, NO robust kernel - this is our "truth"

struct DiamondObservation {
    Eigen::Vector3d point3d;   // Diamond corner in world frame
    Eigen::Vector2d point2d;   // Measured pixel coordinate
};

// ORB Feature observation
// Normal weight, WITH Huber robust kernel - tolerates outliers
struct ORBObservation {
    Eigen::Vector3d point3d;   // 3D point from stereo triangulation
    Eigen::Vector2d point2d;   // Current frame pixel coordinate
};

// ============================================================
// Configuration for Hybrid optimization
// ============================================================
struct HybridConfig {
    // Diamond marker weight (Information Matrix scale)
    // Higher = Diamond pose is more trusted
    double diamondWeight = 10000.0;  // 10^4 as per new_change.md

    // ORB weight (baseline)
    double orbWeight = 1.0;

    // Huber kernel delta for ORB edges
    // Errors below this are treated as inliers (quadratic loss)
    // Errors above are treated as outliers (linear loss)
    double huberDelta = 2.0;  // pixels

    // G2O iterations
    int maxIterations = 20;

    // Verbose output
    bool verbose = false;
};

// ============================================================
// Result of Hybrid optimization
// ============================================================
struct HybridPoseResult {
    // Final optimized pose
    Eigen::Matrix3d rotation = Eigen::Matrix3d::Identity();
    Eigen::Vector3d translation = Eigen::Vector3d::Zero();

    // OpenCV-compatible vectors
    cv::Vec3d rvec = cv::Vec3d(0, 0, 0);
    cv::Vec3d tvec = cv::Vec3d(0, 0, 0);

    // Error metrics
    double initialChi2 = 0;    // Total chi2 before optimization
    double finalChi2 = 0;      // Total chi2 after optimization
    double diamondError = 0;   // Reprojection error of diamond corners (pixels)
    double orbMeanError = 0;   // Mean reprojection error of ORB inliers (pixels)

    // Statistics
    int iterations = 0;
    int numOrbInliers = 0;     // ORB points not suppressed by Huber
    int numOrbOutliers = 0;    // ORB points suppressed by Huber
    bool converged = false;
};

// ============================================================
// HybridPoseSolver: Diamond Prior + ORB Features with G2O
// ============================================================
class HybridPoseSolver {
public:
    HybridPoseSolver();

    // Set camera intrinsics
    void setCameraParams(const cv::Mat& cameraMatrix, const cv::Mat& distCoeffs);

    // Set optimization configuration
    void setConfig(const HybridConfig& config);

    // ============================================================
    // Main optimization function
    // ============================================================
    // Inputs:
    //   - initialRvec, initialTvec: Initial pose guess (from Diamond solvePnP)
    //   - diamondObs: 4 observations from Diamond marker corners
    //   - orbObs: N observations from ORB feature matching
    //
    // Pipeline inside:
    //   1. Build G2O graph with 1 camera pose vertex
    //   2. Add Diamond edges (high weight, no robust kernel)
    //   3. Add ORB edges (normal weight, Huber kernel)
    //   4. Optimize with Levenberg-Marquardt
    //   5. Return refined pose
    // ============================================================
    HybridPoseResult optimize(
        const cv::Vec3d& initialRvec,
        const cv::Vec3d& initialTvec,
        const std::vector<DiamondObservation>& diamondObs,
        const std::vector<ORBObservation>& orbObs
    );

    HybridPoseResult optimizeDiamondOnly(
        const cv::Vec3d& initialRvec,
        const cv::Vec3d& initialTvec,
        const std::vector<DiamondObservation>& diamondObs
    );

private:
    cv::Mat cameraMatrix_;
    cv::Mat distCoeffs_;
    double fx_, fy_, cx_, cy_;
    bool paramsSet_;
    HybridConfig config_;

    // Compute reprojection error for a set of 3D-2D pairs
    double computeReprojError(
        const cv::Vec3d& rvec,
        const cv::Vec3d& tvec,
        const std::vector<Eigen::Vector3d>& points3d,
        const std::vector<Eigen::Vector2d>& points2d
    );
};

#endif
