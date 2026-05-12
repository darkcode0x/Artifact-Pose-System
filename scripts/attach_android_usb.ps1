# =============================================================================
# attach_android_usb.ps1
# Auto-detect Android phone via usbipd, bind+attach to WSL, then run adb reverse.
#
# Chạy từ Windows PowerShell (Terminal thường, KHÔNG cần Admin):
#   powershell -ExecutionPolicy Bypass -File attach_android_usb.ps1
#
# Lần đầu bind có thể cần Admin. Nếu thiếu quyền, script tự chạy lại bằng
# "Run as Administrator" (UAC prompt sẽ hiện).
# =============================================================================

param(
    [int]$Port = 8000,          # Port cần tunnel qua adb reverse
    [switch]$NoWait,            # Không dừng màn hình khi xong
    [string]$WslDistro = ""     # Chỉ định WSL distro, bỏ trống = dùng default
)

# ─── VID (Vendor ID) phổ biến của thiết bị Android ──────────────────────────
$AndroidVIDs = @(
    '18d1',  # Google / Nexus / Pixel (AOSP)
    '04e8',  # Samsung
    '2717',  # Xiaomi / Redmi
    '22b8',  # Motorola
    '0bb4',  # HTC
    '12d1',  # Huawei
    '1004',  # LG
    '0fce',  # Sony
    '2a70',  # OnePlus
    '05c6',  # Qualcomm (nhiều Android dùng)
    '0b05',  # ASUS
    '04dd',  # Sharp
    '2d95',  # vivo
    '22d9',  # OPPO / Realme
    '33bb',  # Realme
    '1bbb',  # ZTE
    'e040',  # Nothing Phone
    '0489'   # Foxconn (một số OEM)
)

# Keyword trong tên device (fallback nếu VID không match)
$AndroidKeywords = 'Android|Phone|ADB|Pixel|Galaxy|Xiaomi|Redmi|Poco|OnePlus|Huawei|OPPO|vivo|Realme|Motorola|Nokia|Nothing|ZTE|HTC|Sony'

# ─── Helper: màu sắc ─────────────────────────────────────────────────────────
function Write-Step($msg)  { Write-Host "  [*] $msg" -ForegroundColor Cyan }
function Write-OK($msg)    { Write-Host "  [+] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  [!] $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "  [X] $msg" -ForegroundColor Red }

function Pause-IfNeeded {
    if (-not $NoWait) {
        Write-Host ""
        Write-Host "  Nhấn Enter để thoát..." -ForegroundColor DarkGray
        Read-Host | Out-Null
    }
}

# ─── Kiểm tra usbipd có trong PATH không ─────────────────────────────────────
function Get-UsbipdPath {
    $cmd = Get-Command usbipd -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    # Thử đường dẫn cài đặt mặc định của usbipd-win
    $default = "$env:ProgramFiles\usbipd-win\usbipd.exe"
    if (Test-Path $default) { return $default }
    return $null
}

# ─── Parse output của usbipd list ────────────────────────────────────────────
function Find-AndroidDevices([string]$usbipdPath) {
    $raw = & $usbipdPath list 2>&1
    $devices = @()

    foreach ($line in ($raw -split "`n")) {
        $line = $line.Trim()
        # Format: BUSID  VID:PID   DEVICE NAME   STATE
        # e.g.:   1-4    18d1:4ee7  Android        Not shared
        if ($line -match '^(\d+-\d+)\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s+(.*?)\s{2,}(.*)$') {
            $busid = $Matches[1]
            $vid   = $Matches[2].ToLower()
            $pid   = $Matches[3].ToLower()
            $name  = $Matches[4].Trim()
            $state = $Matches[5].Trim()

            $byVid  = $AndroidVIDs -contains $vid
            $byName = $name -match $AndroidKeywords

            if ($byVid -or $byName) {
                $devices += [PSCustomObject]@{
                    BusId = $busid
                    Vid   = $vid
                    Pid   = $pid
                    Name  = $name
                    State = $state
                }
            }
        }
    }
    return $devices
}

# ─── Tự restart với quyền Admin nếu cần ─────────────────────────────────────
function Request-AdminIfNeeded {
    $currentPrincipal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    $isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-Warn "Bước 'bind' cần quyền Administrator. Đang khởi động lại với UAC..."
        Start-Sleep -Seconds 1
        $psArgs = "-ExecutionPolicy Bypass -File `"$PSCommandPath`" -Port $Port -NoWait"
        if ($WslDistro) { $psArgs += " -WslDistro $WslDistro" }
        Start-Process powershell -ArgumentList $psArgs -Verb RunAs
        exit 0
    }
}

# ════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Android USB Auto-Attach to WSL       ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 1. Tìm usbipd
$usbipdPath = Get-UsbipdPath
if (-not $usbipdPath) {
    Write-Err "Không tìm thấy usbipd. Cài đặt tại: https://github.com/dorssel/usbipd-win/releases"
    Pause-IfNeeded; exit 1
}
Write-OK "usbipd: $usbipdPath"

# 2. Tìm thiết bị Android
Write-Step "Đang tìm thiết bị Android..."
$devices = Find-AndroidDevices $usbipdPath

if ($devices.Count -eq 0) {
    Write-Err "Không tìm thấy thiết bị Android nào."
    Write-Host "    → Kiểm tra cáp USB đã cắm chưa"
    Write-Host "    → Bật USB Debugging trên điện thoại"
    Write-Host "    → Chọn 'File Transfer' (MTP) khi điện thoại hỏi"
    Write-Host ""
    Write-Host "  Danh sách thiết bị hiện có:" -ForegroundColor DarkGray
    & $usbipdPath list 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    Pause-IfNeeded; exit 1
}

# 3. Chọn thiết bị (nếu nhiều hơn 1)
$device = $null
if ($devices.Count -eq 1) {
    $device = $devices[0]
} else {
    Write-Host "  Tìm thấy $($devices.Count) thiết bị Android:" -ForegroundColor Yellow
    for ($i = 0; $i -lt $devices.Count; $i++) {
        Write-Host "    [$($i+1)] BUSID $($devices[$i].BusId)  $($devices[$i].Vid):$($devices[$i].Pid)  $($devices[$i].Name)  [$($devices[$i].State)]"
    }
    $choice = Read-Host "  Chọn số (Enter = chọn [1])"
    $idx = if ($choice -match '^\d+$') { [int]$choice - 1 } else { 0 }
    $device = $devices[$idx]
}

Write-OK "Chọn: BUSID $($device.BusId) — $($device.Name) ($($device.Vid):$($device.Pid)) [$($device.State)]"

# 4. Bind (cần admin, bỏ qua nếu đã shared)
if ($device.State -notmatch 'Shared|Attached') {
    Request-AdminIfNeeded
    Write-Step "Bind BUSID $($device.BusId)..."
    $bindOut = & $usbipdPath bind --busid $device.BusId 2>&1
    if ($LASTEXITCODE -ne 0 -and $bindOut -notmatch 'already') {
        Write-Warn "bind output: $bindOut"
    } else {
        Write-OK "Bind thành công"
    }
} else {
    Write-OK "Thiết bị đã ở trạng thái '$($device.State)', bỏ qua bind"
}

# 5. Attach vào WSL
Write-Step "Attach BUSID $($device.BusId) vào WSL..."
$wslArg = if ($WslDistro) { "--distribution $WslDistro" } else { "" }
$attachOut = & $usbipdPath attach --wsl $wslArg --busid $device.BusId 2>&1
if ($LASTEXITCODE -ne 0) {
    # Có thể đã attached rồi
    if ($attachOut -match 'already attached|already connected') {
        Write-OK "Thiết bị đã được attach sẵn"
    } else {
        Write-Warn "attach output: $attachOut"
        Write-Warn "Thử tiếp tục adb reverse..."
    }
} else {
    Write-OK "Attach thành công"
}

# 6. Chờ WSL nhận diện device
Write-Step "Chờ WSL nhận device (2 giây)..."
Start-Sleep -Seconds 2

# 7. adb reverse trong WSL
Write-Step "Chạy: adb reverse tcp:$Port tcp:$Port trong WSL..."
$wslCmd = if ($WslDistro) { "wsl -d $WslDistro" } else { "wsl" }

# Restart adb server trước để đảm bảo nhận device mới
& $wslCmd.Split()[0] ($wslCmd.Split()[1..99] + @("adb kill-server")) 2>&1 | Out-Null
Start-Sleep -Seconds 1

$adbDevices = & $wslCmd.Split()[0] ($wslCmd.Split()[1..99] + @("adb devices")) 2>&1
Write-Host "  adb devices:" -ForegroundColor DarkGray
$adbDevices | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }

$reverseOut = & $wslCmd.Split()[0] ($wslCmd.Split()[1..99] + @("adb", "reverse", "tcp:$Port", "tcp:$Port")) 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-OK "adb reverse tcp:$Port tcp:$Port — THÀNH CÔNG"
} else {
    Write-Err "adb reverse thất bại: $reverseOut"
    Write-Host "    Thử chạy thủ công trong WSL: adb reverse tcp:$Port tcp:$Port" -ForegroundColor Yellow
}

# 8. Kết quả
Write-Host ""
Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║   XONG! Tunnel đang hoạt động.         ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Green
Write-Host "  http://127.0.0.1:$Port trên điện thoại → PC:$Port" -ForegroundColor White
Write-Host ""
Write-Host "  Lệnh kiểm tra (trong WSL): adb reverse --list" -ForegroundColor DarkGray

Pause-IfNeeded
