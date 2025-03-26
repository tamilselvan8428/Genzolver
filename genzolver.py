import streamlit as st
import webbrowser
import requests
import time
import os
import json
import google.generativeai as genai
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from collections import defaultdict, deque
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains

# --- 🔐 Gemini API Setup ---
API_KEY = os.getenv("GEMINI_API_KEY")  # Store API key in environment variables
if not API_KEY:
    st.error("❌ API Key is missing. Set GEMINI_API_KEY in your environment variables.")
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
            return {str(p["stat"]["frontend_question_id"]): p["stat"]["question__title_slug"] for p in data["stat_status_pairs"]}
    except Exception as e:
        st.error(f"❌ Error fetching problems: {e}")
    return {}

problems_dict = fetch_problems()

# --- 🧠 Session State ---
st.session_state.setdefault("analytics", defaultdict(lambda: {"attempts": 0, "solutions": []}))
st.session_state.setdefault("problem_history", deque(maxlen=10))
st.session_state.setdefault("solved_problems", set())

# --- 🔗 Utility Functions ---
def get_slug(pid):
    return problems_dict.get(pid)

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
    query = {"query": """
        query getQuestionDetail($titleSlug: String!) {
          question(titleSlug: $titleSlug) { content title }
        }""",
        "variables": {"titleSlug": slug}}
    try:
        res = requests.post("https://leetcode.com/graphql", json=query)
        if res.status_code == 200:
            return BeautifulSoup(res.json()["data"]["question"]["content"], "html.parser").get_text()
    except Exception as e:
        return f"❌ GraphQL error: {e}"
    return "❌ Failed to fetch problem."

# --- 🤖 Gemini AI Solver ---
def solve_with_gemini(pid, lang, text):
    if text.startswith("❌"):
        return "❌ Problem fetch failed."
    prompt = f"""Solve the following LeetCode problem in {lang}:\n{text}\nProvide only the full class definition."""
    try:
        res = model.generate_content(prompt)
        return res.text.strip()
    except Exception as e:
        return f"❌ Gemini Error: {e}"

# --- 🛠 Submit Solution Selenium ---
def submit_solution_and_paste(pid, lang, sol):
    slug = get_slug(pid)
    if not slug:
        st.error("❌ Invalid problem number.")
        return
    url = f"https://leetcode.com/problems/{slug}/"
    options = EdgeOptions()
    options.use_chromium = True
    options.add_argument("--start-maximized")
    options.add_experimental_option("detach", True)

    try:
        driver = webdriver.Edge(service=EdgeService(), options=options)
        driver.get(url)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "monaco-editor")))
        time.sleep(3)
        driver.execute_script("monaco.editor.getModels()[0].setValue('');")
        time.sleep(1)
        driver.execute_script(f"monaco.editor.getModels()[0].setValue({json.dumps(sol)});")
        time.sleep(2)
        editor_element = driver.find_element(By.CLASS_NAME, "monaco-editor")
        editor_element.click()
        time.sleep(1)
        ActionChains(driver).send_keys(Keys.ARROW_RIGHT).perform()
        time.sleep(1)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("`").key_up(Keys.CONTROL).perform()
        st.info("🚀 Sent Run command")
        time.sleep(5)
        try:
            result_element = WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Accepted') or contains(text(),'Wrong Answer')]")
            ))
            st.info(f"🧪 Run Result: {result_element.text.strip()}")
        except TimeoutException:
            st.error("❌ Run result timed out.")
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
