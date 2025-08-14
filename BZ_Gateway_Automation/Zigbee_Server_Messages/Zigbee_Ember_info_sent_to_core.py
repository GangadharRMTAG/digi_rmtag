import pytest
import time
import serial
import re
import csv
import pandas as pd
from SFConnection import get_connection
from playwright.sync_api import sync_playwright
LOG_FILE = 'uart_logs.txt'
open(LOG_FILE, 'w').close()
def log_uart(msg):
    clean_msg = strip_ansi_and_timestamp(msg)
    print(clean_msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(clean_msg + "\n")
def strip_ansi_and_timestamp(log_line):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    line = ansi_escape.sub('', log_line)
    timestamp_prefix = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| ')
    line = timestamp_prefix.sub('', line)
    return line.strip()

DEVICE_CREDENTIALS = {
    "53874770835668991999": "uzMjzm9dBKY3x@ZR",
    "52328298625871380479": "@@fT27u6kWATxGqW",
    "44373003025891983359": "u$6AjeNhVDFbLz!X",
    "54890725700062412799": "G@x7LPSaVi+voKEF",
    "46762288917430403071": "dN3CUgn6!$bEjrxj",
}

@pytest.fixture(scope="module")
def serial_connection():
    COM_PORT = 'COM3'
    BAUD_RATE = 115200
    TIMEOUT = 2

    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=TIMEOUT)
    time.sleep(2)

    yield ser

    ser.close()
    print("\n[Serial Closed]")

def send_cli_command(ser, cmd, wait=1, expected=None, regex=False):
    log_uart(f"\n>> Sending: {cmd}")
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    response = ser.read_all().decode(errors='ignore')
    log_uart(f"<< Response:\n{response}")

    if expected:
        if regex:
            match = re.search(expected, response)
            if match:
                log_uart(f"[✓] Expected regex pattern matched: '{expected}'")
                return True
            else:
                log_uart(f"[✗] Expected regex pattern NOT found: '{expected}'")
                return False
        else:
            if expected in response:
                log_uart(f"[✓] Expected string found: '{expected}'")
                return True
            else:
                log_uart(f"[✗] Expected string NOT found: '{expected}'")
                return False

    return response

def snowflake_login_and_download_csv(device_id, expected_pattern):
    conn = get_connection("gthalang", "xU$I(R#WpFUC9H_6=J^oeiBu")
    id_str = device_id
    query = f"""
        SELECT DATERECEIVED,PACKET_PAYLOAD,RESPONSE_PAYLOAD
        FROM ARCHIVES.KINESIS.V_PACKET_RESPONSE
        WHERE DATERECEIVED BETWEEN '2025-07-31 00:00:00' AND '2025-07-31 23:59:00' AND DEVICEID='52328298625871380479'
        order by DATERECEIVED DESC;
    """
    file_path = "downloaded_result.csv"
    df=pd.read_sql(query, conn)
    df.to_csv(file_path, index=False)
    return file_path

def test_ZigbeeEmberInfoSentToCore(serial_connection, record_property):
    ser = serial_connection

    # 1. Get device ID
    response = send_cli_command(ser, 'id', wait=2)
    match = re.search(r'\d{20}', response)
    device_id = match.group(0)
    password = DEVICE_CREDENTIALS[device_id]

    # 2. Authenticate and prepare environment
    assert send_cli_command(ser, f'pass {password}', wait=2,
                            expected="Password Valid, Security access level 2 granted.")

    assert send_cli_command(ser, 'debug on', wait=2,
                            expected="Enabling external debug UART without auto-off")

    assert send_cli_command(ser, 'blemode down', wait=2,
                            expected="B-Sensor mode set to DOWN.")

    send_cli_command(ser, 'zpmode down', wait=2,
                     expected="Zpoint mode set to: DOWN")

    assert send_cli_command(ser, 'tr 0', wait=2,
                            expected="Disabling transmissions to Core.")

    assert send_cli_command(ser, 'log debug', wait=2,
                            expected="Setting log level to debug for all modules")

    # 3. Ensure clean sfstatus before continuing
    sfstatus_resp = send_cli_command(ser, 'sfstatus', wait=2)
    expected_msg = "0 items in the store and 0 items in the priority queue"
    log_uart(f"Checking sfstatus: {sfstatus_resp}")

    if expected_msg not in sfstatus_resp:
        log_uart("[!] sfstatus not clean, flushing...")
        send_cli_command(ser, 'sfflush store', wait=3)
        sfstatus_resp = send_cli_command(ser, 'sfstatus', wait=2)

    assert expected_msg in sfstatus_resp, "[✗] sfstatus still not clean after flush."

    # 4. Proceed with zpmode up and tr 1 after sfstatus is clean
    assert send_cli_command(ser, 'zpmode up', wait=5,
                            expected="Zpoint mode set to: UP")
    assert send_cli_command(ser, 'tr 1', time.sleep(60),
                            expected="Enabling transmissions to Core")

    # 5. Wait 20 minutes before checking Snowflake
    log_uart("Waiting for 20 minutes to update packets in Snowflake")
    print("Waiting for 20 minutes to update packets in Snowflake")
    time.sleep(1200)  # 20 minutes

    # 6. Download Snowflake CSV
    expected_pattern = "96D2"
    log_uart("Downloading CSV file from Snowflake")
    print("Downloading CSV file from Snowflake")
    csv_file_path = snowflake_login_and_download_csv(device_id, expected_pattern)

    # 7. Validate second row payload
    found = False
    print("Expected hex value in packet from CSV file:", expected_pattern)
    with open(csv_file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        second_row = next(reader, None)

        if second_row and len(second_row) >= 2:
            payload = second_row[1].strip()
            print(f"Second row payload: {payload}")
            if expected_pattern in payload:
                print("Expected value found in second row payload.")
                found = True
            else:
                print("Expected value NOT found in second row payload.")
        else:
            print("Second row not found or invalid.")

    assert found, "Expected pattern not found in the second row payload."

    # 8. Upload log to TestRail
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)

    log_uart("[✓] Test completed successfully.")
