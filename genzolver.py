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
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains

# --- 🔐 Gemini API Setup ---
API_KEY = "AIzaSyAuqflDWBKYP3edhkTH69qoTKJZ_BgbNW8"
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
        if res.status_code == 200:
            html = res.json()["data"]["question"]["content"]
            return BeautifulSoup(html, "html.parser").get_text()
    except Exception as e:
        return f"❌ GraphQL error: {e}"
    return "❌ Failed to fetch problem."

# --- 🤖 Gemini AI Solver ---
def solve_with_gemini(pid, lang, text):
    if text.startswith("❌"):
        return "❌ Problem fetch failed."
    
    prompt = f"""Solve the following LeetCode problem in {lang}:
Problem:  
{text}
Requirements:
- Wrap the solution inside class Solution {{ public: ... }};
- Follow the LeetCode function signature.
- Return only the full class definition with the method inside.
- Do NOT use code fences like ``` or {lang}.
Solution:"""
    
    try:
        res = model.generate_content(prompt)
        return res.text.strip()
    except Exception as e:
        return f"❌ Gemini Error: {e}"

# --- 🚀 Submit Solution to LeetCode via Chrome ---
def submit_solution(pid, lang, solution):
    slug = get_slug(pid)
    if not slug:
        st.error("❌ Invalid problem number.")
        return
    url = f"https://leetcode.com/problems/{slug}/"

    # Chrome WebDriver Setup
    options = ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-popup-blocking")
    options.add_experimental_option("detach", True)

    driver = webdriver.Chrome(service=ChromeService(), options=options)
    driver.get(url)

    try:
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, "monaco-editor")))
        time.sleep(3)
        
        # Clear editor and paste solution
        driver.execute_script("monaco.editor.getModels()[0].setValue('');")
        time.sleep(1)
        driver.execute_script(f"monaco.editor.getModels()[0].setValue({json.dumps(solution)});")
        time.sleep(2)

        # Focus editor
        editor_element = driver.find_element(By.CLASS_NAME, "monaco-editor")
        editor_element.click()
        time.sleep(1)
        
        # Run Code (Ctrl + `)
        actions = ActionChains(driver)
        actions.key_down(Keys.CONTROL).send_keys("`").key_up(Keys.CONTROL).perform()
        st.info("🚀 Running Code...")
        time.sleep(5)

        # Submit Code (Ctrl + Enter)
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        st.info("🚀 Submitting Code...")
        time.sleep(5)
        
        st.success(f"🏆 Problem {pid} submitted successfully!")
        st.session_state.solved_problems.add(pid)
    except WebDriverException as e:
        st.error(f"❌ Selenium Error: {e}")
    finally:
        driver.quit()

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
                submit_solution(pid, lang, solution)
        else:
            st.error("❌ Invalid problem number.")
    else:
        st.error("❌ Use format: Solve LeetCode [problem number]")