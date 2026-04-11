#include "stereo_triangulation.h"

using namespace cv;
using namespace std;
using namespace Eigen;

StereoTriangulator::StereoTriangulator()
    : paramsSet_(false), fx_(0), fy_(0), cx_(0), cy_(0) {}

void StereoTriangulator::setCameraParams(const Mat& cameraMatrix, const Mat& distCoeffs) {
    cameraMatrix_ = cameraMatrix.clone();
    distCoeffs_ = distCoeffs.clone();

    fx_ = cameraMatrix.at<double>(0, 0);
    fy_ = cameraMatrix.at<double>(1, 1);
    cx_ = cameraMatrix.at<double>(0, 2);
    cy_ = cameraMatrix.at<double>(1, 2);

    paramsSet_ = true;
    computeProjectionMatrices();
}

void StereoTriangulator::setConfig(const StereoConfig& config) {
    config_ = config;
    if (paramsSet_) {
        computeProjectionMatrices();
    }
}

void StereoTriangulator::computeProjectionMatrices() {
    // Left camera: at origin, identity rotation
    // P1 = K * [I | 0]
    Mat Rt1 = Mat::eye(3, 4, CV_64F);
    P1_ = cameraMatrix_ * Rt1;

    // P2 = K * [I | t] where t = baseline * direction
    Mat Rt2 = Mat::eye(3, 4, CV_64F);
    Vec3d t = config_.baseline * config_.baselineDirection;
    Rt2.at<double>(0, 3) = -t[0]; 
    Rt2.at<double>(1, 3) = -t[1];
    Rt2.at<double>(2, 3) = -t[2];
    P2_ = cameraMatrix_ * Rt2;
}

TriangulatedPoint StereoTriangulator::triangulatePoint(
    const Point2f& left,
    const Point2f& right
) {
    TriangulatedPoint result;
    result.pointLeft = left;
    result.pointRight = right;
    result.valid = false;

    // Compute disparity (only meaningful for horizontal baseline)
    result.disparity = left.x - right.x;

    if (abs(result.disparity) < config_.minDisparity) {
        return result; 
    }

    // Triangulate using DLT method
    // Build the 4x4 system: A * X = 0
    Mat A(4, 4, CV_64F);

    // Row 0, 1: from left camera
    A.row(0) = left.x * P1_.row(2) - P1_.row(0);
    A.row(1) = left.y * P1_.row(2) - P1_.row(1);

    // Row 2, 3: from right camera
    A.row(2) = right.x * P2_.row(2) - P2_.row(0);
    A.row(3) = right.y * P2_.row(2) - P2_.row(1);

    // SVD to find null space
    Mat w, u, vt;
    SVD::compute(A, w, u, vt, SVD::FULL_UV);

    // Solution is the last row of Vt
    Mat X = vt.row(3).t();

    double W = X.at<double>(3);
    if (abs(W) < 1e-10) {
        return result; 
    }

    double X3d = X.at<double>(0) / W;
    double Y3d = X.at<double>(1) / W;
    double Z3d = X.at<double>(2) / W;

    if (Z3d <= 0) {
        return result; 
    }

    result.point3d = Vector3d(X3d, Y3d, Z3d);
    result.depth = Z3d;

    // Compute reprojection error
    // Project 3D point back to both images
    vector<Point3f> pt3d = {Point3f(X3d, Y3d, Z3d)};

    vector<Point2f> projLeft, projRight;
    Vec3d rvecZero(0, 0, 0);
    Vec3d tvecZero(0, 0, 0);
    Vec3d tvecRight = -(config_.baseline * config_.baselineDirection);

    projectPoints(pt3d, rvecZero, tvecZero, cameraMatrix_, distCoeffs_, projLeft);
    projectPoints(pt3d, rvecZero, tvecRight, cameraMatrix_, distCoeffs_, projRight);

    double errLeft = norm(Point2f(projLeft[0].x - left.x, projLeft[0].y - left.y));
    double errRight = norm(Point2f(projRight[0].x - right.x, projRight[0].y - right.y));
    result.reprojError = (errLeft + errRight) / 2.0;

    // Quality check
    if (result.reprojError <= config_.maxReprojError) {
        result.valid = true;
    }

    return result;
}

StereoTriangulationResult StereoTriangulator::triangulate(
    const vector<Point2f>& pointsLeft,
    const vector<Point2f>& pointsRight
) {
    StereoTriangulationResult result;
    result.numValid = 0;
    result.numRejected = 0;
    result.meanDepth = 0;
    result.meanReprojError = 0;

    if (!paramsSet_ || pointsLeft.size() != pointsRight.size()) {
        return result;
    }

    double sumDepth = 0;
    double sumError = 0;

    for (size_t i = 0; i < pointsLeft.size(); i++) {
        TriangulatedPoint tp = triangulatePoint(pointsLeft[i], pointsRight[i]);
        result.points.push_back(tp);

        if (tp.valid) {
            result.numValid++;
            sumDepth += tp.depth;
            sumError += tp.reprojError;
        } else {
            result.numRejected++;
        }
    }

    if (result.numValid > 0) {
        result.meanDepth = sumDepth / result.numValid;
        result.meanReprojError = sumError / result.numValid;
    }

    return result;
}
