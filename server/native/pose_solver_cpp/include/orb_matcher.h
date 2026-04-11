#ifndef ORB_MATCHER_H
#define ORB_MATCHER_H

#include <opencv2/opencv.hpp>
#include <opencv2/features2d.hpp>
#include <Eigen/Core>
#include <vector>

// ORB Matching Configuration
struct MatchConfig {
    enum MatchMethod { BF_HAMMING, FLANN_LSH };
    MatchMethod method = BF_HAMMING;

    float ratioThreshold = 0.75f;
    bool crossCheck = false;
    int minMatches = 10;
    int maxHammingDistance = 64;
};

// 3D-2D Match (for pose estimation)
struct Match3D2D {
    Eigen::Vector3d point3d;   // 3D point from triangulation
    Eigen::Vector2d point2d;   // 2D point in current frame
    int refIdx;                // Index in reference 3D point cloud
    float matchDistance;       // Descriptor distance
};

struct Match3D2DResult {
    std::vector<Match3D2D> matches;
    int numMatches;
    float meanDistance;
};


// // ORBMatcher: Match features between frames
class ORBMatcher {
public:
    ORBMatcher();

    void setConfig(const MatchConfig& config);

    // Match current ORB features with stored 3D reference
    // Returns 3D-2D correspondences for G2O optimization
    Match3D2DResult matchWith3DReference(
        const std::vector<cv::KeyPoint>& currentKeypoints,
        const cv::Mat& currentDescriptors,
        const std::vector<Eigen::Vector3d>& refPoints3d,
        const cv::Mat& refDescriptors
    );

    // Brute-force match with ratio test (returns DMatch indices)
    std::vector<cv::DMatch> matchBruteForce(
        const cv::Mat& desc1,
        const cv::Mat& desc2
    );

private:
    MatchConfig config_;
    cv::Ptr<cv::DescriptorMatcher> matcher_;

    void initMatcher();
    std::vector<cv::DMatch> filterByRatioTest(
        const std::vector<std::vector<cv::DMatch>>& knnMatches
    );
};

#endif
