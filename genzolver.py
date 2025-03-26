import streamlit as st
import webbrowser
import requests
import time
import os
import json
import subprocess
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
API_KEY = "AIzaSyAuqflDWBKYP3edhkTH69qoTKJZ_BgbNW8"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# --- 🌐 Streamlit UI Setup ---
st.title("🤖 LeetCode Auto-Solver & Analytics Chatbot (Gemini AI)")
st.write("Type Solve LeetCode [problem number] or ask me anything!")

# --- 🗂 Fetch LeetCode Problems ---
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

# --- 🧠 Session State ---
st.session_state.setdefault("analytics", defaultdict(lambda: {"attempts": 0, "solutions": []}))
st.session_state.setdefault("problem_history", deque(maxlen=10))
st.session_state.setdefault("solved_problems", set())

# --- 🔗 Utility Functions ---
def get_slug(pid): return problems_dict.get(pid)

def open_problem(pid):
    slug = get_slug(pid)
    if slug:
        url = f"https://leetcode.com/problems/{slug}/"
        webbrowser.open(url)
        return url
    st.error("❌ Invalid problem number.")
    return None

# --- 📝 Fetch Problem Statement ---
def get_problem_statement(slug):
    try:
        query = {
            "query": """
            query getQuestionDetail($titleSlug: String!) {
              question(titleSlug: $titleSlug) { content title }
            }""",
            "variables": {"titleSlug": slug}
        }
        res = requests.post("https://leetcode.com/graphql", json=query)
        res.raise_for_status()
        data = res.json()

        if "data" in data and "question" in data["data"]:
            html = data["data"]["question"]["content"]
            return BeautifulSoup(html, "html.parser").get_text()
        else:
            return "❌ Unexpected problem format."

    except requests.RequestException as e:
        return f"❌ GraphQL API error: {e}"

# --- 🤖 Gemini AI Solver ---
def solve_with_gemini(pid, lang, text):
    if text.startswith("❌"):
        return "❌ Problem fetch failed."
    
    prompt = f"""Solve the following LeetCode problem in {lang}:
    
**Problem Description:**  
{text}

**Requirements:**
- Implement a solution following LeetCode's function signature.
- Wrap the solution in an appropriate class.
- Ensure correctness and efficiency.
- Return only the complete function/class definition.

**Solution:**"""

    try:
        res = model.generate_content(prompt)
        sol_raw = res.text.strip()
        return sol_raw
    except Exception as e:
        return f"❌ Gemini Error: {e}"

# --- 📥 WebDriver Setup ---
def setup_webdriver():
    driver_path = "/tmp/msedgedriver.exe"

    if not os.path.exists(driver_path):
        driver_url = "https://msedgedriver.azureedge.net/124.0.2478.67/edgedriver_win64.zip"
        
        try:
            subprocess.run(["wget", driver_url, "-O", "/tmp/edgedriver.zip"], check=True)
            subprocess.run(["unzip", "/tmp/edgedriver.zip", "-d", "/tmp/"], check=True)
            subprocess.run(["chmod", "+x", driver_path], check=True)
        except subprocess.CalledProcessError as e:
            st.error(f"❌ WebDriver setup failed: {e}")
            return None

    return driver_path

# --- 🛠 Submit Solution Selenium ---
def submit_solution_and_paste(pid, lang, sol):
    slug = get_slug(pid)
    if not slug:
        st.error("❌ Invalid problem number.")
        return
    url = f"https://leetcode.com/problems/{slug}/"

    driver_path = setup_webdriver()
    if not driver_path:
        st.error("❌ WebDriver setup failed.")
        return

    options = EdgeOptions()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Edge(service=EdgeService(driver_path), options=options)
        driver.get(url)

        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "monaco-editor")))
        time.sleep(3)

        # Clear editor and paste solution
        driver.execute_script("monaco.editor.getModels()[0].setValue('');")
        time.sleep(1)
        escaped_sol = json.dumps(sol)
        driver.execute_script(f"monaco.editor.getModels()[0].setValue({escaped_sol});")
        time.sleep(2)

        # Run and submit
        actions = ActionChains(driver)
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        st.info("🚀 Submitted Solution!")
        time.sleep(5)

        driver.quit()

    except WebDriverException as e:
        st.error(f"❌ Selenium Error: {e}")

# --- 🎯 User Input Handling ---
user_input = st.text_input("Your command or question:")

if user_input.lower().startswith("solve leetcode"):
    tokens = user_input.strip().split()
    if len(tokens) == 3 and tokens[2].isdigit():
        pid = tokens[2]
        slug = get_slug(pid)
        if slug:
            lang = st.selectbox("Language", ["cpp", "python", "java", "javascript", "csharp"], index=0)
            if st.button("Generate & Submit Solution"):
                st.session_state.problem_history.append(pid)
                open_problem(pid)
                text = get_problem_statement(slug)
                solution = solve_with_gemini(pid, lang, text)
                st.code(solution, language=lang)
                submit_solution_and_paste(pid, lang, solution)
        else:
            st.error("❌ Invalid problem number.")
    else:
        st.error("❌ Use format: Solve LeetCode [problem number]")
elif user_input:
    try:
        res = model.generate_content(user_input)
        st.chat_message("assistant").write(res.text)
    except Exception as e:
        st.error(f"❌ Gemini Error: {e}")
