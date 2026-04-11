cmake_minimum_required(VERSION 3.10)
project(pose_solver_cpp)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POLICY_DEFAULT_CMP0072 NEW)

# Prefer modern FindPython flow for pybind11 on newer CMake versions.
set(PYBIND11_FINDPYTHON ON)

find_package(OpenCV REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(g2o REQUIRED)
find_package(Python REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 REQUIRED)


pybind11_add_module(pose_solver_cpp
    bindings.cpp
    src/quadtree.cpp
    src/hybrid_pose_solver.cpp
    src/stereo_triangulation.cpp
    src/orb_matcher.cpp
    src/deviation_calculator.cpp
)

target_include_directories(pose_solver_cpp PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${OpenCV_INCLUDE_DIRS}
    ${EIGEN3_INCLUDE_DIR}
)

target_link_libraries(pose_solver_cpp PRIVATE 
    ${OpenCV_LIBS}
    Eigen3::Eigen
    g2o::core
    g2o::stuff
    g2o::types_sba
    g2o::types_slam3d
    g2o::solver_pcg
)

message(STATUS "--------------------------------------------")
message(STATUS "OpenCV version: ${OpenCV_VERSION}")
message(STATUS "G2O found: ${g2o_FOUND}")
message(STATUS "Eigen3 include: ${EIGEN3_INCLUDE_DIR}")
message(STATUS "--------------------------------------------")