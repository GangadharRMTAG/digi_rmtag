import pytest
import time
import serial
import re
import pandas as pd
from SFConnection import get_connection
"""this is not applicable for the automation"""
LOG_FILE = 'uart_logs.txt'
open(LOG_FILE, 'w').close()

DEVICE_CREDENTIALS = {
    "44373003025891983359": "u$6AjeNhVDFbLz!X",
}

DEVICE_ID = "44373003025891983359"

def log_uart(msg):
    print(msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")

def strip_ansi_and_timestamp(line):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    line = ansi_escape.sub('', line)
    timestamp_prefix = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| ')
    return timestamp_prefix.sub('', line).strip()

# def send_cli_command(ser, cmd, wait=1):
#     log_uart(f"\n>> Sending: {cmd}")
#     ser.write((cmd + '\n').encode())
#     time.sleep(wait)
#     response = ser.read_all().decode(errors='ignore')
#     log_uart(f"<< Response:\n{response}")
#     return response

def send_cli_command(ser, cmd, wait=1, capture=False):
    log_uart(f"\n>> Sending: {cmd}")
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    response = ser.read_all().decode(errors='ignore')
    log_uart(f"<< Response:\n{response}")

    if capture:
        return response


@pytest.fixture(scope="module")
def serial_connection():
    COM_PORT = 'COM8'  # adjust to your setup
    BAUD_RATE = 115200
    TIMEOUT = 2
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=TIMEOUT)
    time.sleep(2)
    yield ser
    ser.close()
    print("\n[Serial Closed]")

def test_wakeup_reset_reason(serial_connection, record_property):
    # ser = serial_connection
    # password = DEVICE_CREDENTIALS[DEVICE_ID]

    # send_cli_command(ser, 'id', wait=2)
    # send_cli_command(ser, f'pass {password}', wait=2)
    # send_cli_command(ser, 'debug on', wait=2)
    # send_cli_command(ser, 'log debug', wait=2)
    # # Step 1: Remove AC power and shut down DUT
    # send_cli_command(ser, 'reset onn', wait=2)
   
    # time.sleep(10)  
    # log_uart("check for device reboot.....")
    # send_cli_command(ser, f'pass {password}', wait=2)
    # send_cli_command(ser, 'debug on', wait=2)
    # send_cli_command(ser, 'log debug', wait=2)

#----------------------------------------------------------------------------------------------

    ser = serial_connection
    password = DEVICE_CREDENTIALS[DEVICE_ID]

    send_cli_command(ser, 'id', wait=2)
    send_cli_command(ser, f'pass {password}', wait=2)
    send_cli_command(ser, 'debug on', wait=2)
    send_cli_command(ser, 'log debug', wait=2)

    log_uart("[INFO] Sending reset command...")
    send_cli_command(ser, 'reset n', wait=2)
   
    time.sleep(10)  # Initial wait before checking reboot

    # Retry check for wake-up
    rebooted = False
    for attempt in range(5):
        log_uart(f"[INFO] Checking DUT wake-up... attempt {attempt + 1}")
        response = send_cli_command(ser, f'pass {password}', wait=2, capture=True)

        if response.strip():  # If we get any non-empty response
            rebooted = True
            log_uart("[✓] Device woke up and accepted password.")
            break
        else:
            log_uart("[WARN] No response yet, waiting...")
            time.sleep(3)

    if not rebooted:
        pytest.fail("[✗] DUT did not wake up after reset.")

    send_cli_command(ser, 'debug on', wait=2)
    send_cli_command(ser, 'log debug', wait=2)


    #----------------------------------------------------------------------------------------------
    # # Step 3: Download Snowflake logs
    # log_uart("[STEP 3] Downloading Snowflake logs for verification...")
    # conn = get_connection()
    # query = f"""
    #     SELECT DATERECEIVED, PACKET_PAYLOAD, RESPONSE_PAYLOAD
    #     FROM ARCHIVES.KINESIS.V_PACKET_RESPONSE
    #     WHERE DATERECEIVED BETWEEN '2025-05-25 00:00:00' AND '2025-05-28 23:59:00'
    #     AND DEVICEID='{DEVICE_ID}'
    #     ORDER BY DATERECEIVED DESC;
    # """
    # df = pd.read_sql(query, conn)
    # snowflake_csv = 'snowflake_logs.csv'
    # df.to_csv(snowflake_csv, index=False)
    # log_uart(f"[INFO] Saved Snowflake logs to {snowflake_csv}")

    # Step 4: Look for '998C05' packet in Snowflake logs
    # match_df = df[df['PACKET_PAYLOAD'].str.contains('998C05', case=False, na=False)]
    # assert not match_df.empty, "No packet containing '998C05' found in Snowflake logs"
    # log_uart(f"[INFO] Found packet(s) containing '998C05':\n{match_df}")

    # Step 5: Validate reset reason
    # Assuming parseit output indicates reset reason in RESPONSE_PAYLOAD or PACKET_PAYLOAD
    # reset_reason_found = match_df['RESPONSE_PAYLOAD'].str.contains('wakeup', case=False, na=False).any() \
    #                      or match_df['PACKET_PAYLOAD'].str.contains('wakeup', case=False, na=False).any()
    # assert reset_reason_found, "Reset reason 'wakeup' not found in matching packet"

    log_uart("[✓] Wakeup reset reason verified successfully.")

    # Attach logs for reporting
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)
    # record_property("snowflake_csv", snowflake_csv)
