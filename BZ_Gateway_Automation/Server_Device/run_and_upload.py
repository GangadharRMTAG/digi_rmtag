import subprocess
import pytest
from playwright.sync_api import sync_playwright
import time
 #pytest -s .\run_and_upload.py
@pytest.fixture(scope="module")
def run_pytest_and_upload():
    print("Running test case...")
    pytest_cmd = ["pytest", "--junitxml=reports/junit-report.xml", "reset.py"]
    pytest_status = subprocess.run(pytest_cmd)
    print("Uploading test results to TestRail.")
    upload_cmd = ["trcli", "-y", "-c", "trcli-config.yml", "parse_junit", "-f", "reports/junit-report.xml"]
    upload_status = subprocess.run(upload_cmd)
    return pytest_status.returncode, upload_status.returncode
def open_testrail_dashboard():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://rmtagsolution2025.testrail.io/index.php?/auth/login/")
        time.sleep(1)
        page.get_by_test_id("loginIdName").fill("rmtag.team1@gmail.com")
        time.sleep(1)
        page.get_by_test_id("loginPasswordFormDialog").fill("Rmtag@123")
        time.sleep(1)
        page.get_by_test_id("loginButtonPrimary").click()
        time.sleep(2)
        page.get_by_role("link", name="demoTest").click()
        time.sleep(2)
        page.get_by_role("link", name="Pytest Testrail").first.click()
        time.sleep(1)
        time.sleep(10)
        context.close()
        browser.close()
@pytest.mark.order("last")
def test_upload_and_open_browser(run_pytest_and_upload):
    pytest_return, upload_return = run_pytest_and_upload
    if pytest_return != 0:
        print("Test case failed")
    else:
        print("Test passed")
    if upload_return != 0:
        print("Upload to TestRail failed")
    else:
        print("Test results uploaded to TestRail.")
    print("Opening TestRail dashboard.")
    open_testrail_dashboard()
    assert upload_return == 0, "TestRail upload failed"