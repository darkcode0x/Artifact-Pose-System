###############################################################################
# Stage 1: Build C++ pose_solver_cpp voi libs cua container
###############################################################################
FROM python:3.10-slim AS cpp-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake pkg-config git \
        libopencv-dev \
        libeigen3-dev \
        libsuitesparse-dev \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Build g2o from source (Debian libg2o-dev khong co cmake config files)
RUN git clone --depth 1 https://github.com/RainerKuemmerle/g2o.git /tmp/g2o \
    && cd /tmp/g2o \
    && mkdir build && cd build \
    && cmake .. -DCMAKE_BUILD_TYPE=Release -DG2O_BUILD_EXAMPLES=OFF -DG2O_BUILD_APPS=OFF \
    && make -j"$(nproc)" \
    && make install \
    && ldconfig \
    && rm -rf /tmp/g2o

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
        libopencv-dev libsuitesparse-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy g2o runtime libs tu builder stage
COPY --from=cpp-builder /usr/local/lib/libg2o* /usr/local/lib/
RUN ldconfig

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# Copy .so tu builder stage — link voi dung libs cua container
COPY --from=cpp-builder /build/pose_solver_cpp/build/pose_solver_cpp*.so \
    /app/app/modules/artifact_pose/

EXPOSE 8000

CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8000"]