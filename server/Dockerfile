###############################################################################
# Stage 1: Build C++ pose_solver_cpp voi libs cua container
###############################################################################
FROM python:3.10-slim AS cpp-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake pkg-config \
        libopencv-dev \
        libeigen3-dev \
        libg2o-dev \
        libsuitesparse-dev \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install pybind11[global]

WORKDIR /build
COPY native/pose_solver_cpp/ ./pose_solver_cpp/

RUN cd pose_solver_cpp \
    && rm -rf build \
    && mkdir -p build && cd build \
    && cmake .. \
    && make -j"$(nproc)"

###############################################################################
# Stage 2: Runtime
###############################################################################
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
        libopencv-dev libg2o-dev libsuitesparse-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# Copy .so tu builder stage — link voi dung libs cua container
COPY --from=cpp-builder /build/pose_solver_cpp/build/pose_solver_cpp*.so \
    /app/app/modules/artifact_pose/

EXPOSE 8000

CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8000"]