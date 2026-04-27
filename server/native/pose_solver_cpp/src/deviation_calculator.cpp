#include "deviation_calculator.h"
#include <cmath>

using namespace cv;
using namespace std;
using namespace Eigen;

constexpr double RAD2DEG = 180.0 / M_PI;
constexpr double DEG2RAD = M_PI / 180.0;

DeviationCalculator::DeviationCalculator() {}

void DeviationCalculator::setConfig(const DeviationConfig& config) {
    config_ = config;
}

PoseDeviation DeviationCalculator::calculate(
    const Vec3d& rvecGolden,
    const Vec3d& tvecGolden,
    const Vec3d& rvecCurrent,
    const Vec3d& tvecCurrent
) {
    // Convert rvec to rotation matrix
    Mat R_golden_mat, R_current_mat;
    Mat rvec_g = (Mat_<double>(3,1) << rvecGolden[0], rvecGolden[1], rvecGolden[2]);
    Mat rvec_c = (Mat_<double>(3,1) << rvecCurrent[0], rvecCurrent[1], rvecCurrent[2]);
    Rodrigues(rvec_g, R_golden_mat);
    Rodrigues(rvec_c, R_current_mat);

    // Convert to Eigen
    Matrix3d R_golden, R_current;
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            R_golden(i, j) = R_golden_mat.at<double>(i, j);
            R_current(i, j) = R_current_mat.at<double>(i, j);
        }
    }

    Vector3d T_golden(tvecGolden[0], tvecGolden[1], tvecGolden[2]);
    Vector3d T_current(tvecCurrent[0], tvecCurrent[1], tvecCurrent[2]);

    return calculate(R_golden, T_golden, R_current, T_current);
}

PoseDeviation DeviationCalculator::calculate(
    const Eigen::Matrix3d& R_golden,
    const Eigen::Vector3d& T_golden,
    const Eigen::Matrix3d& R_current,
    const Eigen::Vector3d& T_current
) {
    PoseDeviation dev;
    Vector3d T_diff = T_current - T_golden;

    dev.deltaX = T_diff.x();
    dev.deltaY = T_diff.y();
    dev.deltaZ = T_diff.z();

    dev.translationMag = T_diff.norm();

    // R_deviation = R_current * R_golden^T
    // This gives us the relative rotation from golden to current
    Matrix3d R_diff = R_current * R_golden.transpose();

    double roll, pitch, yaw;
    rotationToEuler(R_diff, roll, pitch, yaw);

    dev.deltaTilt = roll;
    dev.deltaPan  = pitch;
    dev.deltaRoll = yaw;

    dev.rotationMag = sqrt(dev.deltaPan * dev.deltaPan +
                           dev.deltaTilt * dev.deltaTilt +
                           dev.deltaRoll * dev.deltaRoll);

    dev.withinTransTolerance = (dev.translationMag < config_.transTolerance);
    dev.withinRotTolerance = (dev.rotationMag < config_.rotTolerance);
    dev.withinTolerance = dev.withinTransTolerance && dev.withinRotTolerance;

    return dev;
}

void DeviationCalculator::rotationToEuler(
    const Eigen::Matrix3d& R,
    double& roll,   
    double& pitch,  
    double& yaw     
) {
    // More accurate extraction:
    double sy = sqrt(R(0,0) * R(0,0) + R(1,0) * R(1,0));

    bool singular = sy < 1e-6;

    if (!singular) {
        roll = atan2(R(2,1), R(2,2));
        pitch = atan2(-R(2,0), sy);
        yaw = atan2(R(1,0), R(0,0));
    } else {
        // Gimbal lock: pitch ≈ ±90°
        roll = atan2(-R(1,2), R(1,1));
        pitch = atan2(-R(2,0), sy);
        yaw = 0;
    }

    // Convert to degrees
    roll *= RAD2DEG;
    pitch *= RAD2DEG;
    yaw *= RAD2DEG;
}


// Apply servo dead zone + rounding to a rotation angle.
// Rounds to the nearest multiple of servoMinDeg.
// Angles that would round to 0 are zeroed (dead zone).
static double applyServoConstraint(double angleDeg, double servoMinDeg) {
    if (servoMinDeg <= 0.0) return angleDeg;
    double rounded = std::round(angleDeg / servoMinDeg) * servoMinDeg;
    return rounded;
    // Note: std::round naturally handles the dead zone — values with
    // |angle| < 0.5*servoMinDeg round to 0 (e.g. 0.3° with 1° step → 0°)
}

MotorCommand deviationToMotorCommand(
    const PoseDeviation& dev,
    double stepsPerMm,
    double servoMinDeg,
    bool   sequentialMode
) {
    MotorCommand cmd;

    // --- Translation: convert m → mm → steps ---
    cmd.moveX = dev.deltaX * 1000.0 * stepsPerMm;
    cmd.moveZ = dev.deltaZ * 1000.0 * stepsPerMm;

    // --- Rotation: apply hardware dead zone + rounding ---
    // Angles smaller than half a servo step are zeroed to avoid
    // infinite oscillation around the tolerance boundary.
    cmd.rotatePan  = applyServoConstraint(dev.deltaPan,  servoMinDeg);
    cmd.rotateTilt = applyServoConstraint(dev.deltaTilt, servoMinDeg);

    // --- Priority ---
    bool needTrans = !dev.withinTransTolerance;
    bool needRot   = !dev.withinRotTolerance;

    if (!needTrans && !needRot) {
        cmd.priority = 0;   // ALIGNED
    } else if (needTrans && !needRot) {
        cmd.priority = 1;   // Translation only
    } else if (!needTrans && needRot) {
        cmd.priority = 2;   // Rotation only
    } else {
        cmd.priority = 3;   // Both needed
    }

    // --- Sequential mode: translation first ---
    // When both translation and rotation are needed (priority=3),
    // zero out rotation this step. The next correction iteration will
    // re-evaluate pose and handle rotation once translation is done.
    // This prevents the two DoF from coupling and amplifying each other.
    if (sequentialMode && cmd.priority == 3) {
        cmd.rotatePan  = 0.0;
        cmd.rotateTilt = 0.0;
    }

    return cmd;
}
