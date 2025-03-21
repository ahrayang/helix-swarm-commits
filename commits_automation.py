import os
import json
import logging
import time
import tkinter as tk
import webbrowser
import threading
from datetime import datetime, timedelta

from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

CONFIG_FILE = "config.json"

def load_credentials():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError("Login info file not found: " + CONFIG_FILE)
    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        credentials = json.load(file)
    username = credentials.get("username")
    password = credentials.get("password")
    if not username or not password:
        raise ValueError("config.json must contain username and password")
    return username, password

# utc_to_kst_ampm 함수 추가 - UTC 시간을 KST 기준 AM/PM 형식으로 변환
def utc_to_kst_ampm(utc_str):
    try:
        # fromisoformat가 ISO 형식의 문자열을 datetime 객체로 변환합니다.
        dt_utc = datetime.fromisoformat(utc_str)
        # UTC에서 9시간 더해서 KST로 변환합니다.
        dt_kst = dt_utc + timedelta(hours=9)
        # 예: "2025-03-20 오후 04:18" 형식으로 반환 (12시간제, %p는 AM/PM)
        return dt_kst.strftime("%Y-%m-%d %p %I:%M")
    except Exception:
        return ""

# 사용자가 KST 기준으로 선택한 날짜를 Swarm에서 사용하는 UTC 날짜(@YYYY/MM/DD)로 변환
def convert_kst_date_to_utc_str(kst_date):
    dt_kst = datetime.combine(kst_date, datetime.min.time())
    dt_utc = dt_kst - timedelta(hours=9)
    return dt_utc.strftime("%Y/%m/%d")

def get_kst_range_str():
    start_date = start_date_entry.get_date()
    end_date = end_date_entry.get_date()
    return (start_date.strftime("%Y/%m/%d"), end_date.strftime("%Y/%m/%d"))

def get_utc_range_str():
    start_date = start_date_entry.get_date()
    end_date = end_date_entry.get_date()
    start_utc = convert_kst_date_to_utc_str(start_date)
    end_utc = convert_kst_date_to_utc_str(end_date)
    return "@" + start_utc + ",@" + end_utc

def update_guide_label(*args):
    kst_start, kst_end = get_kst_range_str()
    utc_range = get_utc_range_str()
    guide_text.set(f"KST: {kst_start} ~ {kst_end}\n"
                   f"UTC로는: {utc_range}\n"
                   "Swarm은 이 UTC 범위를 조회합니다.")

def start_crawling():
    range_value = get_utc_range_str()
    threading.Thread(target=crawl_data, args=(range_value,), daemon=True).start()

def crawl_data(range_value):
    driver = None
    try:
        USERNAME, PASSWORD = load_credentials()
        logging.info(f"Swarm Range (UTC): {range_value}")

        options = Options()
        # options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        driver.get("http://perforce.alt9.io/login")
        username_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        password_input = driver.find_element(By.NAME, "password")
        username_input.send_keys(USERNAME)
        password_input.send_keys(PASSWORD)
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='button']")
        login_button.click()
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "react-swarm-app-container"))
        )

        commits_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, '//*[@id="react-swarm-app-container"]/div/div[2]/div[2]/ul/li[6]')
            )
        )
        commits_btn.click()
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, '//*[@id="react-swarm-app-container"]//span[contains(@class, "module-id") and text()="commits"]')
            )
        )
        time.sleep(1)

        range_input_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "range"))
        )
        range_input_elem.click()
        range_input_elem.clear()
        range_input_elem.send_keys(range_value)
        range_input_elem.send_keys(Keys.RETURN)
        time.sleep(2)

        commits_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "commits"))
        )
        scroll_attempts = 0
        previous_last = ""
        while True:
            commit_rows = commits_container.find_elements(By.CSS_SELECTOR, "tr")
            if not commit_rows:
                break
            try:
                last_td = commit_rows[-1].find_elements(By.TAG_NAME, "td")
                current_last = last_td[0].text.strip() if last_td else ""
            except Exception:
                current_last = ""
            if current_last == previous_last:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
            if scroll_attempts >= 5:
                logging.info("No new commits loaded after repeated scrolling; stopping.")
                break
            previous_last = current_last
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            commits_container = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "commits"))
            )

        commit_rows = commits_container.find_elements(By.CSS_SELECTOR, "tr")
        for item in treeview.get_children():
            treeview.delete(item)
        row_link_info.clear()

        for row in commit_rows:
            tds = row.find_elements(By.TAG_NAME, "td")
            if len(tds) < 4:
                continue
            try:
                commit_link = tds[0].find_element(By.TAG_NAME, "a")
                commit_id = commit_link.text.strip()
            except:
                commit_id = tds[0].text.strip()
            anchor_tags = row.find_elements(By.TAG_NAME, "a")
            hrefs = [a.get_attribute("href") for a in anchor_tags if a.get_attribute("href")]
            user = tds[1].text.strip()
            description = tds[2].text.strip()
            try:
                time_span = tds[3].find_element(By.CSS_SELECTOR, "span.timeago")
                utc_time = time_span.get_attribute("title")
            except:
                utc_time = tds[3].text.strip()
            kst_time = utc_to_kst_ampm(utc_time)
            row_id = treeview.insert(
                "", "end",
                values=(commit_id, user, description, utc_time, kst_time)
            )
            if hrefs:
                treeview.item(row_id, tags=("has_link",))
                row_link_info[row_id] = hrefs

        messagebox.showinfo("Complete", f"Found {len(treeview.get_children())} commits.")
    except Exception as e:
        messagebox.showerror("Crawling Error", "Error occurred: " + str(e))
        logging.error("Error during crawling: " + str(e))
    finally:
        if driver:
            driver.quit()

def on_double_click(event):
    selected_item = treeview.focus()
    if not selected_item:
        return
    if selected_item in row_link_info:
        links = row_link_info[selected_item]
        if links:
            webbrowser.open(links[0])

root = tk.Tk()
root.title("Swarm Crawler (KST→UTC 안내)")

style = ttk.Style(root)
style.theme_use("clam")
style.configure("Treeview", font=("Helvetica", 10))

frame_top = ttk.Frame(root)
frame_top.pack(pady=5, fill="x")

ttk.Label(frame_top, text="Start Date (KST):").pack(side="left", padx=5)
start_date_entry = DateEntry(frame_top, date_pattern="yyyy/mm/dd")
start_date_entry.pack(side="left", padx=5)
ttk.Label(frame_top, text="End Date (KST):").pack(side="left", padx=5)
end_date_entry = DateEntry(frame_top, date_pattern="yyyy/mm/dd")
end_date_entry.pack(side="left", padx=5)

guide_text = tk.StringVar()
guide_label = ttk.Label(root, textvariable=guide_text, foreground="red", font=("Helvetica", 12, "bold"))
guide_label.pack(pady=5)

def update_guide(*args):
    kst_start, kst_end = get_kst_range_str()
    utc_range = get_utc_range_str()
    guide_text.set(f"선택한 KST 기간: {kst_start} ~ {kst_end}\n"
                   f"Swarm에서 조회되는 UTC 범위: {utc_range}\n"
                   "참고: KST은 UTC보다 +9시간 빠릅니다.")
start_date_entry.bind("<<DateEntrySelected>>", update_guide)
end_date_entry.bind("<<DateEntrySelected>>", update_guide)

btn_run = ttk.Button(root, text="Start Crawling", command=start_crawling)
btn_run.pack(pady=10)

columns = ("Change", "User", "Description", "UTC", "KST(AM/PM)")
treeview = ttk.Treeview(root, columns=columns, show="headings", height=20)
treeview.heading("Change", text="Change")
treeview.heading("User", text="User")
treeview.heading("Description", text="Description")
treeview.heading("UTC", text="Committed(UTC)")
treeview.heading("KST(AM/PM)", text="Committed(KST)")
treeview.column("Change", width=80, anchor="w")
treeview.column("User", width=80, anchor="w")
treeview.column("Description", width=400, anchor="w")
treeview.column("UTC", width=150, anchor="w")
treeview.column("KST(AM/PM)", width=180, anchor="w")

scrollbar_y = ttk.Scrollbar(root, orient="vertical", command=treeview.yview)
treeview.configure(yscrollcommand=scrollbar_y.set)
treeview.pack(side="left", fill="both", expand=True)
scrollbar_y.pack(side="right", fill="y")

treeview.bind("<Double-1>", on_double_click)
treeview.tag_configure("has_link", foreground="blue")

row_link_info = {}

root.mainloop()
