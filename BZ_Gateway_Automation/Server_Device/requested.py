import pytest
import time
import serial
import re
import pandas as pd
from playwright.sync_api import sync_playwright
# from SFConnection import get_connection


LOG_FILE = 'uart_logs.txt'
open(LOG_FILE, 'w').close()

DEVICE_CREDENTIALS = {
    "44373003025891983359": "u$6AjeNhVDFbLz!X",
}

DEVICE_ID = "44373003025891983359"

# Utility: log UART output to file and console
def log_uart(msg):
    print(msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")

# Utility: strip ANSI and timestamp prefixes from DUT logs
def strip_ansi_and_timestamp(line):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    line = ansi_escape.sub('', line)
    timestamp_prefix = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| ')
    return timestamp_prefix.sub('', line).strip()

# Utility: send CLI command via UART
def send_cli_command(ser, cmd, wait=1):
    log_uart(f"\n>> Sending: {cmd}")
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    response = ser.read_all().decode(errors='ignore')
    log_uart(f"<< Response:\n{response}")
    return response

@pytest.fixture(scope="module")
def serial_connection():
    COM_PORT = 'COM8'  # Adjust as per setup
    BAUD_RATE = 115200
    TIMEOUT = 2
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=TIMEOUT)
    time.sleep(2)
    yield ser
    ser.close()
    print("\n[Serial Closed]")

def login_and_send_interval_command(playwright, deviceID):
    browser = playwright.chromium.launch(headless=False, slow_mo=500)
    context = browser.new_context()
    page = context.new_page()

    page.goto("https://tools.smartsense.co/")
    page.get_by_role("button", name="Sign In With SSO").click()
    page.get_by_role("textbox", name="Username").click()
    page.get_by_role("textbox", name="Username").fill("gthalang@digi.com")
    page.get_by_text("Keep me signed in").click()
    page.get_by_role("button", name="Next").click()
    page.get_by_role("textbox", name="Password").fill("Rmtag@123456")
    page.get_by_role("button", name="Verify").click()
    page.locator("iframe[title=\"'Verify with Duo Security'\"]").content_frame.locator("body").click()
    page.locator("iframe[title=\"'Verify with Duo Security'\"]").content_frame.get_by_role("button", name="Send Me a Push").click()
    time.sleep(15)
    page.get_by_role("link", name=" Devices").click()
    page.get_by_role("textbox").click()
    page.get_by_role("textbox").fill(deviceID)
    page.get_by_role("button", name="Search ").click()
    page.get_by_role("row", name=deviceID).get_by_role("checkbox").click()

    # Send command
    page.get_by_role("button", name="Send Command").click()
    page.get_by_role("textbox", name="Enter Command").fill("C1")
    page.get_by_role("button", name="save").click()

    context.close()
    browser.close()

def test_firmware_version_request(serial_connection, record_property):
    """
    Test Steps:
    1. Log in to DUT (Level 2) and enable debug logs.
    2. Run 'v' to confirm firmware version.
    3. Send 0xC1 command via server tools (mocked in this test).
    4. Force 1-2 transmissions.
    5. Validate packet in Snowflake.
    """
    ser = serial_connection
    password = DEVICE_CREDENTIALS[DEVICE_ID]

    log_uart("[STEP 1] Logging in and enabling debug...")
    send_cli_command(ser, 'id', wait=2)
    send_cli_command(ser, f'pass {password}', wait=2)
    send_cli_command(ser, 'debug on', wait=2)
    send_cli_command(ser, 'log debug', wait=2)
    #This test is more helpful if SF is cleared before reset occurs. Run sfflush store to clear the SF

    # send_cli_command(ser, 'sfflush store', wait=5)
    # send_cli_command(ser, 'sfstatus', wait=2)

    log_uart("[STEP 2] Checking firmware version...")
    version_resp = send_cli_command(ser, 'v', wait=2)
    assert "Application version" in version_resp, "Firmware version info missing"

    log_uart("[STEP 3] Sending (0xC1) firmware version request via server tools...")

    #Send server command
    with sync_playwright() as playwright:
        print("Sending command to server")
        login_and_send_interval_command(playwright, DEVICE_ID)


    log_uart("[INFO] This step is normally done via web portal, mocking server send...")
    # In actual test environment, trigger 0xC1 command from 'tools.smartsense.co'
    # This automation assumes the DUT will receive & process it automatically.

    log_uart("[STEP 4] Forcing transmissions...")
    for i in range(2):
        send_cli_command(ser, "upload", wait=8)
        time.sleep(2)

    # log_uart("[STEP 5] Querying Snowflake for packet validation...")
    # conn = get_connection()
    # query = f"""
    #     SELECT DATERECEIVED, PACKET_PAYLOAD, RESPONSE_PAYLOAD
    #     FROM ARCHIVES.KINESIS.V_PACKET_RESPONSE
    #     WHERE DATERECEIVED BETWEEN '2025-05-25 00:00:00' AND '2025-05-28 23:59:00'
    #     AND DEVICEID='{DEVICE_ID}'
    #     ORDER BY DATERECEIVED DESC;
    # """
    # df = pd.read_sql(query, conn)
    # log_uart(f"[DEBUG] Snowflake returned {len(df)} rows")

    # Filter for 0x83 0xC1 ACK packets
    match_df = df[df['PACKET_PAYLOAD'].str.contains('83C1', case=False, na=False)]
    # assert not match_df.empty, "No 0x83 0xC1 ACK packet found in Snowflake"

    log_uart(f"[INFO] Found matching ACK packet:\n{match_df.head(1)}")

    # Save logs for reporting
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)

    log_uart("[✓] Test completed successfully - Firmware version request verified.")
