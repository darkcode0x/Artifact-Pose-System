#!/usr/bin/env bash
# =============================================================================
# wsl_adb_setup.sh
# Chạy từ WSL sau khi usbipd đã attach thiết bị.
# Dùng khi bạn đã chạy attach_android_usb.ps1 hoặc đã attach thủ công.
#
# Usage:
#   ./scripts/wsl_adb_setup.sh           # tunnel port 8000 (mặc định)
#   ./scripts/wsl_adb_setup.sh 8080      # tunnel port khác
# =============================================================================

set -e

PORT="${1:-8000}"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}=== WSL adb Setup (port $PORT) ===${NC}"

# 1. Kiểm tra adb có không
if ! command -v adb &>/dev/null; then
    echo -e "${RED}[X] adb không tìm thấy trong PATH.${NC}"
    echo "    Cài: sudo apt install adb  hoặc  snap install android-tools"
    exit 1
fi

# 2. Restart adb server (đảm bảo nhận USB device mới gắn vào)
echo -e "${CYAN}[*] Restart adb server...${NC}"
adb kill-server 2>/dev/null || true
sleep 1
adb start-server 2>/dev/null

# 3. Hiển thị danh sách devices
echo -e "${CYAN}[*] Thiết bị đang kết nối:${NC}"
adb devices

# 4. Kiểm tra có device nào không
DEVICE_COUNT=$(adb devices | grep -c "device$" || true)
if [[ "$DEVICE_COUNT" -eq 0 ]]; then
    echo -e "${YELLOW}[!] Không thấy thiết bị nào.${NC}"
    echo "    → Kiểm tra điện thoại đã chọn 'Allow USB Debugging'"
    echo "    → Chạy lại: attach_android_usb.ps1 (Windows) để attach USB"
    exit 1
fi

# 5. Thiết lập adb reverse
echo -e "${CYAN}[*] Thiết lập adb reverse tcp:$PORT tcp:$PORT ...${NC}"
if adb reverse "tcp:$PORT" "tcp:$PORT"; then
    echo -e "${GREEN}[+] Tunnel đang hoạt động: http://127.0.0.1:$PORT trên điện thoại → PC:$PORT${NC}"
else
    echo -e "${RED}[X] adb reverse thất bại.${NC}"
    exit 1
fi

# 6. Hiển thị danh sách tunnel đang active
echo ""
echo -e "${CYAN}[*] Các tunnel đang active:${NC}"
adb reverse --list

echo ""
echo -e "${GREEN}=== Xong! Bạn có thể chạy app Flutter bây giờ. ===${NC}"
echo -e "    flutter run --dart-define=API_BASE_URL=http://127.0.0.1:$PORT"
