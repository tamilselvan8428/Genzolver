import streamlit as st
import webbrowser
import requests
import time
import os
import json
from collections import defaultdict, deque
import google.generativeai as genai
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains

# --- 🔐 Gemini API Setup ---
API_KEY = "YOUR_GEMINI_API_KEY"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# --- 🌐 Streamlit UI Setup ---
st.title("🤖 LeetCode Auto-Solver & Analytics Chatbot (Gemini AI)")
st.write("Type Solve LeetCode [problem number] or ask me anything!")

# --- 🗂 Cache LeetCode Problems ---
@st.cache_data
def fetch_problems():
    try:
        res = requests.get("https://leetcode.com/api/problems/all/")
        if res.status_code == 200:
            data = res.json()
            return {str(p["stat"]["frontend_question_id"]): p["stat"]["question__title_slug"]
                    for p in data["stat_status_pairs"]}
    except Exception as e:
        st.error(f"❌ Error fetching problems: {e}")
    return {}

problems_dict = fetch_problems()

# --- 🛠 Submit Solution Selenium ---
def submit_solution_and_paste(pid, lang, sol):
    slug = problems_dict.get(pid)
    if not slug:
        st.error("❌ Invalid problem number.")
        return
    url = f"https://leetcode.com/problems/{slug}/"

    # --- User-Configurable WebDriver Path ---
    driver_path = st.text_input("Enter your WebDriver Path:")

    if not driver_path:
        st.warning("⚠ Please enter a valid WebDriver path.")
        return

    options = EdgeOptions()
    options.use_chromium = True
    options.add_argument("--start-maximized")
    options.add_experimental_option("detach", True)

    try:
        driver = webdriver.Edge(service=EdgeService(driver_path), options=options)
        driver.get(url)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "monaco-editor")))
        time.sleep(3)

        # Clear and paste solution into editor
        driver.execute_script("monaco.editor.getModels()[0].setValue('');")
        time.sleep(1)
        driver.execute_script(f"monaco.editor.getModels()[0].setValue({json.dumps(sol)});")
        time.sleep(2)

        # Submit Solution
        actions = ActionChains(driver)
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        st.info("🚀 Sent Submit command (Ctrl + Enter)")
    except WebDriverException as e:
        st.error(f"❌ Selenium Error: {e}")
