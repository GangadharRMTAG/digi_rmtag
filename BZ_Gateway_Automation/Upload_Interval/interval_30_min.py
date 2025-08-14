import pytest
import time
import serial
import re
import pandas as pd
from SFConnection import get_connection
from playwright.sync_api import sync_playwright
#successfully completed and uploaded in test rail
# timing for snoflake UTC Time = 9:15 => 13/8/25
LOG_FILE = 'uart_logs.txt'
open(LOG_FILE, 'w').close()

DEVICE_CREDENTIALS = {
    "44373003025891983359": "u$6AjeNhVDFbLz!X"
}

def log_uart(msg):
    print(msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + "\n")

def strip_ansi_and_timestamp(log_line):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    line = ansi_escape.sub('', log_line)
    timestamp_prefix = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| ')
    line = timestamp_prefix.sub('', line)
    return line.strip()

def send_cli_command(ser, cmd, wait=1):
    log_uart(f"\n>> Sending: {cmd}")
    ser.write((cmd + '\n').encode())
    time.sleep(wait)
    response = ser.read_all().decode(errors='ignore')
    log_uart(f"<< Response:\n{response}")
    return response

@pytest.fixture(scope="module")
def serial_connection():
    COM_PORT = 'COM7'
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
    time.sleep(10)
    page.get_by_role("link", name=" Devices").click()
    page.get_by_role("textbox").click()
    page.get_by_role("textbox").fill(deviceID)
    page.get_by_role("button", name="Search ").click()
    page.get_by_role("row", name=deviceID).get_by_role("checkbox").click()

    page.get_by_role("button", name="Send Command").click()
    page.get_by_role("textbox", name="Enter Command").fill("6A60000708")
    page.get_by_role("button", name="save").click()

    context.close()
    browser.close()

def test_update_upload_interval_30min(serial_connection, record_property):
    ser = serial_connection
    device_id = "44373003025891983359"
    password = DEVICE_CREDENTIALS[device_id]

    send_cli_command(ser, f'pass {password}', wait=2)
    send_cli_command(ser, 'debug on', wait=2)
    send_cli_command(ser, 'log debug', wait=2)

    with sync_playwright() as playwright:
        print("Sending command to server")
        login_and_send_interval_command(playwright, device_id)

    for _ in range(3):
        send_cli_command(ser, 'tr 2', wait=3)
        time.sleep(5)

    upload_resp = send_cli_command(ser, 'upload', wait=2)
    assert "1800s" in upload_resp and "Interval Type is 0" in upload_resp, "Upload interval not updated correctly"

    log_uart("Waiting to verify 30-minute intervals between transmissions...")
    
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        log_contents = f.read()
        record_property("testrail_comment", log_contents)
        record_property("testrail_attachment", LOG_FILE)

    log_uart("[✓] Test completed successfully.")
