#!/usr/bin/env bash
set -euo pipefail

EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)
      EXECUTE=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: bash infra/ubuntu/setup_cuda_tensorrt.sh [--execute]" >&2
      exit 2
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AUTOWARE_WS="${AUTOWARE_WS:-$HOME/zmf_ws/projects/autoware_universe/autoware}"
CUDA_DEFAULTS="${AUTOWARE_WS}/ansible/roles/cuda/defaults/main.yaml"
TENSORRT_DEFAULTS="${AUTOWARE_WS}/ansible/roles/tensorrt/defaults/main.yaml"

if [[ -z "${http_proxy:-}" && -f "$HOME/.local/share/zmf/clash_proxy_env.sh" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.local/share/zmf/clash_proxy_env.sh"
fi

CUDA_VERSION=""
if [[ -f "$CUDA_DEFAULTS" ]]; then
  CUDA_VERSION="$(sed -n 's/^cuda_version: *"\(.*\)"/\1/p' "$CUDA_DEFAULTS")"
fi
CUDA_VERSION="${CUDA_VERSION:-12.8}"

if [[ "$(uname -m)" == "aarch64" ]]; then
  if [[ -f "$TENSORRT_DEFAULTS" ]]; then
    TENSORRT_VERSION="$(grep -oP "'\K[^']+(?=' if)" "$TENSORRT_DEFAULTS")"
  else
    TENSORRT_VERSION=""
  fi
else
  if [[ -f "$TENSORRT_DEFAULTS" ]]; then
    TENSORRT_VERSION="$(grep -oP "else '\K[^']+" "$TENSORRT_DEFAULTS")"
  else
    TENSORRT_VERSION=""
  fi
fi
TENSORRT_VERSION="${TENSORRT_VERSION:-10.8.0.43-1+cuda12.8}"

CUDA_VERSION_DASHED="${CUDA_VERSION//./-}"
ARCH="$(dpkg --print-architecture)"
case "$ARCH" in
  amd64) CUDA_REPO_ARCH="x86_64" ;;
  arm64|aarch64) CUDA_REPO_ARCH="sbsa" ;;
  *)
    echo "[FAIL] Unsupported architecture: ${ARCH}" >&2
    exit 1
    ;;
esac

CUDA_KEYRING_URL="https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/${CUDA_REPO_ARCH}/cuda-keyring_1.1-1_all.deb"

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "[FAIL] nvidia-smi is not available. Install or repair the NVIDIA driver first." >&2
  exit 1
fi

CURRENT_DRIVER="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n 1 | tr -d ' ')"
CURRENT_DRIVER_MAJOR="${CURRENT_DRIVER%%.*}"

CUDA_PACKAGES=(
  "cuda-command-line-tools-${CUDA_VERSION_DASHED}"
  "cuda-minimal-build-${CUDA_VERSION_DASHED}"
  "libcusparse-${CUDA_VERSION_DASHED}"
  "libcublas-${CUDA_VERSION_DASHED}"
  "libcurand-${CUDA_VERSION_DASHED}"
  "libnpp-${CUDA_VERSION_DASHED}"
  "libnvjpeg-${CUDA_VERSION_DASHED}"
  "libcusparse-dev-${CUDA_VERSION_DASHED}"
  "libcublas-dev-${CUDA_VERSION_DASHED}"
  "libcurand-dev-${CUDA_VERSION_DASHED}"
  "cuda-nvml-dev-${CUDA_VERSION_DASHED}"
  "cuda-nvrtc-dev-${CUDA_VERSION_DASHED}"
  "libnpp-dev-${CUDA_VERSION_DASHED}"
  "libnvjpeg-dev-${CUDA_VERSION_DASHED}"
  "cuda-nvprof-${CUDA_VERSION_DASHED}"
)

TENSORRT_PACKAGES=(
  "libnvinfer10=${TENSORRT_VERSION}"
  "libnvinfer-plugin10=${TENSORRT_VERSION}"
  "libnvonnxparsers10=${TENSORRT_VERSION}"
  "libnvinfer-dev=${TENSORRT_VERSION}"
  "libnvinfer-plugin-dev=${TENSORRT_VERSION}"
  "libnvinfer-headers-dev=${TENSORRT_VERSION}"
  "libnvinfer-headers-plugin-dev=${TENSORRT_VERSION}"
  "libnvonnxparsers-dev=${TENSORRT_VERSION}"
)

TENSORRT_HOLDS=(
  libnvinfer10
  libnvinfer-plugin10
  libnvonnxparsers10
  libnvinfer-dev
  libnvinfer-plugin-dev
  libnvinfer-headers-dev
  libnvinfer-headers-plugin-dev
  libnvonnxparsers-dev
)

append_line_once() {
  local file="$1"
  local line="$2"
  touch "$file"
  if ! grep -Fxq "$line" "$file"; then
    printf '%s\n' "$line" >>"$file"
  fi
}

run_cmd() {
  echo "+ $*"
  if [[ "$EXECUTE" -eq 1 ]]; then
    "$@"
  fi
}

echo "Preparing CUDA + TensorRT for Autoware on Ubuntu 22.04"
echo "Repo root: ${REPO_ROOT}"
echo "Autoware workspace: ${AUTOWARE_WS}"
echo "Current NVIDIA driver: ${CURRENT_DRIVER}"
echo "Target CUDA toolkit: ${CUDA_VERSION}"
echo "Target TensorRT: ${TENSORRT_VERSION}"
echo "CUDA keyring URL: ${CUDA_KEYRING_URL}"
echo "EXECUTE=${EXECUTE}"

if [[ "${CURRENT_DRIVER_MAJOR:-0}" -lt 570 ]]; then
  echo "[WARN] The repository CUDA role documents driver 570+ for CUDA ${CUDA_VERSION}."
  echo "[WARN] This helper will not change your current driver automatically."
fi

if [[ -n "${http_proxy:-}" ]]; then
  echo "Using proxy: ${http_proxy}"
else
  echo "Using direct network access"
fi

cat <<EOF

Planned steps:
1. Download the NVIDIA CUDA keyring for Ubuntu 22.04 (${CUDA_REPO_ARCH})
2. Install the keyring with sudo
3. Install CUDA ${CUDA_VERSION} runtime and development packages
4. Register Vulkan, OpenGL, and OpenCL NVIDIA vendor files
5. Install TensorRT ${TENSORRT_VERSION}
6. Hold TensorRT packages to keep them pinned
7. Add CUDA PATH / LD_LIBRARY_PATH exports to ~/.bashrc and ~/.profile
8. Verify nvcc and TensorRT libraries
EOF

TMPDIR_PATH="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_PATH"' EXIT
KEYRING_DEB="${TMPDIR_PATH}/cuda-keyring_1.1-1_all.deb"

run_cmd curl -fL --retry 3 --retry-delay 2 -o "$KEYRING_DEB" "$CUDA_KEYRING_URL"
run_cmd sudo -E dpkg -i "$KEYRING_DEB"
run_cmd sudo -E apt-get update
run_cmd sudo -E apt-get install -y "${CUDA_PACKAGES[@]}"
run_cmd sudo -E install -d -m 0755 /etc/vulkan/icd.d /etc/glvnd/egl_vendor.d /etc/OpenCL/vendors
run_cmd sudo -E curl -fL --retry 3 --retry-delay 2 -o /etc/vulkan/icd.d/nvidia_icd.json https://gitlab.com/nvidia/container-images/vulkan/raw/dc389b0445c788901fda1d85be96fd1cb9410164/nvidia_icd.json
run_cmd sudo -E chmod 0644 /etc/vulkan/icd.d/nvidia_icd.json
run_cmd sudo -E curl -fL --retry 3 --retry-delay 2 -o /etc/glvnd/egl_vendor.d/10_nvidia.json https://gitlab.com/nvidia/container-images/opengl/raw/5191cf205d3e4bb1150091f9464499b076104354/glvnd/runtime/10_nvidia.json
run_cmd sudo -E chmod 0644 /etc/glvnd/egl_vendor.d/10_nvidia.json
run_cmd sudo -E bash -lc 'printf "%s\n" "libnvidia-opencl.so.1" > /etc/OpenCL/vendors/nvidia.icd'
run_cmd sudo -E chmod 0644 /etc/OpenCL/vendors/nvidia.icd
run_cmd sudo -E apt-get install -y "${TENSORRT_PACKAGES[@]}"
run_cmd sudo -E apt-mark hold "${TENSORRT_HOLDS[@]}"

if [[ "$EXECUTE" -eq 1 ]]; then
  append_line_once "$HOME/.bashrc" 'export PATH="/usr/local/cuda/bin:$PATH"'
  append_line_once "$HOME/.bashrc" 'export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"'
  append_line_once "$HOME/.profile" 'export PATH="/usr/local/cuda/bin:$PATH"'
  append_line_once "$HOME/.profile" 'export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"'

  echo
  echo "Verification:"
  bash -lc 'source "$HOME/.profile" >/dev/null 2>&1 || true; command -v nvcc; nvcc --version | sed -n "1,4p"; echo "---"; dpkg -l | egrep "cuda-command-line-tools|cuda-minimal-build|libnvinfer10|libnvinfer-dev" || true; echo "---"; ldconfig -p | egrep "libnvinfer|libcudart|libcublas|libcusparse" || true'
else
  echo
  echo "Dry run only. Re-run with:"
  echo "  bash infra/ubuntu/setup_cuda_tensorrt.sh --execute"
fi
