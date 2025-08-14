import re
import time
import io
import pytest
import serial
import pandas as pd  
"""
This test case is failed. As  expected value 4 got 3 after failed transmission 
"""

LOG_FILE = "uart_logs.txt"
open(LOG_FILE, "w", encoding="utf-8").close()

# === CONFIG ===
SERIAL_PORT = "COM8"          
BAUD_RATE = 115200
TIMEOUT = 2   
DEVICE_CREDENTIALS = {
    "44373003025891983359": "u$6AjeNhVDFbLz!X",
}
WAIT_SHORT = 8
WAIT_MED = 30
WAIT_LONG = 90


def log_uart(msg: str):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
TS_PREFIX_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d+\s*\|\s*")

def strip_ansi_and_timestamp(line: str) -> str:
    line = ANSI_RE.sub("", line)
    line = TS_PREFIX_RE.sub("", line)
    return line.strip()

def open_serial(port=SERIAL_PORT, baud=BAUD_RATE, timeout=TIMEOUT):
    ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)
    time.sleep(1.5)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    return ser

def read_all_now(ser):
    try:
        raw = ser.read_all()
        if not raw:
            return ""
        return raw.decode(errors="ignore")
    except Exception:
        out = []
        while ser.in_waiting:
            try:
                out.append(ser.readline().decode(errors="ignore"))
            except Exception:
                break
        return "".join(out)

def send_cli_command(ser, cmd: str, wait: float = 1.0, read_timeout: float = 5.0) -> str:

    log_uart(f"\n>> Sending: {cmd}")
    ser.reset_input_buffer()
    ser.write((cmd + "\n").encode())
    time.sleep(wait)
    end_time = time.time() + read_timeout
    response = ""
    while time.time() < end_time:
        chunk = read_all_now(ser)
        if chunk:
            response += chunk
        time.sleep(0.15)
    cleaned = "".join(strip_ansi_and_timestamp(l) for l in response.splitlines() if l.strip())
    log_uart(f"<< Response:\n{cleaned}\n")
    return cleaned

def wait_for_pattern(ser, pattern: re.Pattern, timeout: float) -> (bool, str):

    buffer = ""
    end = time.time() + timeout
    while time.time() < end:
        chunk = read_all_now(ser)
        if chunk:
            buffer += chunk
            m = pattern.search(buffer)
            if m:
                return True, buffer
        time.sleep(0.2)
    return False, buffer

def extract_upload_info_from_text(text: str):

    type_re = re.compile(r"Current\s+Interval\s+Type\s*(?:is|:)?\s*(\d+)", re.IGNORECASE)
    int_re1 = re.compile(r"Current\s+Upload\s+Interval\s*(?:is|:)?\s*(\d+)\s*s?", re.IGNORECASE)
    int_re2 = re.compile(r"Current\s+Interval\s*is\s*(\d+)\s*s?", re.IGNORECASE)
    t = type_re.search(text)
    i = int_re1.search(text) or int_re2.search(text)
    upload_type = t.group(1) if t else None
    upload_interval = int(i.group(1)) if i else None
    return upload_type, upload_interval

def timestamp_now_iso():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

@pytest.fixture(scope="module")
def serial_connection():
    ser = open_serial()
    yield ser
    try:
        ser.close()
    except Exception:
        pass
    log_uart("[Serial Closed]")

def test_upload_type4_ac_power(serial_connection, record_property):
    ser = serial_connection
    device_id = "44373003025891983359"
    password = DEVICE_CREDENTIALS[device_id]

    log_uart(f"[TEST START] {timestamp_now_iso()} - device {device_id}")

    send_cli_command(ser, f"pass {password}", wait=1.5, read_timeout=4)
    send_cli_command(ser, "debug on", wait=0.8, read_timeout=3)
    send_cli_command(ser, "log debug", wait=0.8, read_timeout=3)

    acpg_out = send_cli_command(ser, "acpg", wait=1.0, read_timeout=6)
    log_uart(f"[DEBUG] Raw acpg output: {repr(acpg_out)}")
    if not re.search(r"AC power detected", acpg_out, re.IGNORECASE):

        ok, buf = wait_for_pattern(ser, re.compile(r"AC power detected", re.IGNORECASE), timeout=8)
        assert ok, f"AC power not detected — ensure AC is connected. Recent buffer:\n{buf}"
        acpg_out += buf

    log_uart("[STEP 1] AC power confirmed.")

    apn_resp = send_cli_command(ser, "network set_apn badapn", wait=1.2, read_timeout=6)

    pattern_pdp = re.compile(r"PDP Event:.*detach|PDP Event:|Network initiated network detach", re.IGNORECASE)
    pattern_apn_ok = re.compile(r"Successfully updated.*APN|Successfully set default APN|APN update pending", re.IGNORECASE)
    found_pdp = bool(pattern_pdp.search(apn_resp))
    found_apn_ok = bool(pattern_apn_ok.search(apn_resp))

    if not (found_pdp or found_apn_ok):
        # poll for a bit longer to collect asynchronous logs
        ok, buf = wait_for_pattern(ser, re.compile(r"PDP Event:|detach|Successfully updated.*APN|APN update", re.IGNORECASE), timeout=15)
        apn_resp += buf
        found_pdp = bool(pattern_pdp.search(apn_resp))
        found_apn_ok = bool(pattern_apn_ok.search(apn_resp))

    assert (found_pdp or found_apn_ok), f"APN change not confirmed. Output:\n{apn_resp}"
    send_cli_command(ser, "mon", wait=1.0, read_timeout=6)
    ok, _ = wait_for_pattern(ser, re.compile(r"PDP Event:|NW DETACH|NW detach|CEREG: 0", re.IGNORECASE), timeout=12)
    log_uart("[STEP 2] APN changed to badapn and modem restarted (mon) — PDP detach expected.")
    upload_resp = send_cli_command(ser, "upload", wait=1.0, read_timeout=6)
    upload_type, upload_interval = extract_upload_info_from_text(upload_resp)

    if not upload_type or not upload_interval:
        ok, buf = wait_for_pattern(ser, re.compile(r"Current\s+Upload\s+Interval|Current\s+Interval\s+Type|Current Upload Interval|Current Interval Type", re.IGNORECASE), timeout=40)
        if ok:
            upload_resp += buf
            upload_type, upload_interval = extract_upload_info_from_text(upload_resp)

    log_uart(f"[INFO] Parsed upload info -> type: {upload_type}, interval: {upload_interval}")

    assert upload_type is not None, f"Expected upload type value not found in logs. Recent logs:\n{upload_resp}"
    assert upload_type == "4", f"Expected upload type 4, got {upload_type}. Raw:\n{upload_resp}"
    assert upload_interval is not None and isinstance(upload_interval, int), f"Upload interval could not be determined. Raw:\n{upload_resp}"

    log_uart(f"[STEP 3] Upload type is 4 and interval is {upload_interval} sec.")

    sensors_resp = send_cli_command(ser, "sensors", wait=1.0, read_timeout=6)
    sensors_pattern = re.compile(r"sensors: Forcing a measurement interval|Forcing a measurement interval|Reading sensors", re.IGNORECASE)
    if not sensors_pattern.search(sensors_resp):
        ok, buf = wait_for_pattern(ser, sensors_pattern, timeout=8)
        sensors_resp += buf
        assert ok, f"Expected sensors forcing measurement log not found. Raw:\n{sensors_resp}"

    log_uart("[STEP 4] Sensors forcing log verified.")
    upload_attempt_patterns = re.compile(r"Attempting upload|Upload started|Upload attempt|Sending packet|Performing upload|Upload attempt in", re.IGNORECASE)

    start_wait = time.time()
    log_uart(f"[STEP 5] Waiting ~{upload_interval + 20}sec for next upload attempt (interval + margin).")
    found = False
    attempt_time = None
    buffer_acc = ""

    max_wait = upload_interval + 30
    end_wait = time.time() + max_wait
    while time.time() < end_wait:
        chunk = read_all_now(ser)
        if chunk:
            buffer_acc += chunk
            if upload_attempt_patterns.search(buffer_acc):
                found = True
                attempt_time = time.time()
                break
        time.sleep(0.4)

    waited = time.time() - start_wait
    log_uart(f"[STEP 5] Waited {waited:.1f}s. Upload attempt found: {found}")

    assert found, f"No upload attempt log observed within {max_wait} seconds. Buffer:\n{buffer_acc}"

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        log_contents = f.read()
    record_property("testrail_comment", log_contents)
    record_property("testrail_attachment", LOG_FILE)

    log_uart(f"[✓] Test completed successfully for upload type 4 scenario. Attempt time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(attempt_time))}")
    