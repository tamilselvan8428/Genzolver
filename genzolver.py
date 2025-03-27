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
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# --- 🔐 API Key ---
API_KEY = os.getenv("GEMINI_API_KEY", st.secrets["GEMINI_API_KEY"])
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# --- 🌐 Streamlit UI ---
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

# --- 🛠 Auto Run & Submit Solution ---
def auto_run_submit(pid, lang, solution):
    if not solution or solution.startswith("❌"):
        st.error("❌ Solution not generated correctly.")
        return

    slug = problems_dict.get(pid)
    if not slug:
        st.error("❌ Invalid problem number.")
        return
    
    url = f"https://leetcode.com/problems/{slug}/"
    st.info(f"🌍 Opening LeetCode Problem: {url}")

    try:
        options = webdriver.EdgeOptions()
        options.add_argument("start-maximized")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        # Run Headless mode only if deploying on a server
        if "STREAMLIT_SERVER_MODE" in os.environ:
            options.add_argument("--headless")

        driver = webdriver.Edge(EdgeChromiumDriverManager().install(), options=options)
        driver.get(url)

        # Wait for page to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "monaco-editor")))

        # Select language
        try:
            lang_selector = driver.find_element(By.CLASS_NAME, "language-selector")
            lang_selector.click()
            time.sleep(1)
            lang_option = driver.find_element(By.XPATH, f"//div[text()='{lang.capitalize()}']")
            lang_option.click()
        except:
            st.warning("⚠️ Language selection failed. Defaulting to previous selection.")

        # Locate the code editor and paste the solution
        editor = driver.find_element(By.CLASS_NAME, "monaco-editor")
        editor.click()
        time.sleep(1)

        # Send keyboard shortcuts to select all, delete, and paste the solution
        editor.send_keys(Keys.CONTROL + "a")
        editor.send_keys(Keys.BACKSPACE)
        editor.send_keys(solution)

        # Click "Run" button
        run_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Run')]")
        run_button.click()
        st.info("🚀 Running the solution...")

        # Wait for run to complete
        time.sleep(10)

        # Auto-submit by simulating "Ctrl + Enter"
        submit_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Submit')]")
        submit_button.send_keys(Keys.CONTROL + Keys.RETURN)  # Auto-submit using Ctrl+Enter

        st.success(f"✅ Solution for Problem {pid} has been submitted successfully!")
        driver.quit()

    except WebDriverException as e:
        st.error(f"❌ WebDriver Error: {e}")
