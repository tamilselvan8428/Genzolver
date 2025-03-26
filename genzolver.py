import streamlit as st
import subprocess
import sys
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
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# --- 🔧 Auto-Install Missing Dependencies ---
def install_package(package):
    try:
        __import__(package)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", package])

# Ensure required packages are installed
install_package("google-generativeai")
install_package("streamlit")
install_package("selenium")
install_package("beautifulsoup4")
install_package("webdriver-manager")

# --- 🔐 Secure Gemini API Key ---
API_KEY = st.secrets["api"]["gemini_key"]  # Load from Streamlit Secrets
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# --- 🌐 Streamlit UI ---
st.title("🤖 LeetCode Auto-Solver & Analytics Chatbot (Gemini AI)")
st.write("Type `Solve LeetCode [problem number]` or ask me anything!")

# --- 🗂 Cache LeetCode Problems ---
@st.cache_data(show_spinner=False)
def fetch_problems():
    url = "https://leetcode.com/api/problems/all/"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        return {str(p["stat"]["frontend_question_id"]): p["stat"]["question__title_slug"]
                for p in data["stat_status_pairs"]}
    except requests.RequestException as e:
        st.error(f"❌ Error fetching LeetCode problems: {e}")
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
*Problem:*  
{text}
*Requirements:*
- Wrap the solution inside `class Solution {{ public: ... }};`
- Follow the LeetCode function signature.
- Return only the full class definition with the method inside.
- Do NOT use code fences like ``` or ```{lang}.
*Solution:*"""
    
    try:
        res = model.generate_content(prompt)
        sol_raw = res.text.strip()

        # Remove any code fences
        lines = sol_raw.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]

        cleaned_solution = "\n".join(lines).strip()

        # Save solution
        st.session_state.analytics[pid]["solutions"].append(cleaned_solution)
        st.session_state.analytics[pid]["attempts"] += 1

        return cleaned_solution
    except Exception as e:
        return f"❌ Gemini Error: {e}"

# --- 🛠 Submit Solution Using Selenium ---
def submit_solution_and_paste(pid, lang, sol):
    slug = get_slug(pid)
    if not slug:
        st.error("❌ Invalid problem number.")
        return
    url = f"https://leetcode.com/problems/{slug}/"

    # Setup WebDriver
    options = EdgeOptions()
    options.use_chromium = True
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager().install()), options=options)
        driver.get(url)

        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "monaco-editor")))
        time.sleep(3)

        # Paste solution into editor
        driver.execute_script("monaco.editor.getModels()[0].setValue('');")
        time.sleep(1)
        escaped_sol = json.dumps(sol)
        driver.execute_script(f"monaco.editor.getModels()[0].setValue({escaped_sol});")
        time.sleep(2)

        # Submit
        actions = ActionChains(driver)
        actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        st.info("🚀 Submitted solution (Ctrl + Enter)")
        time.sleep(5)

        st.success(f"🏆 Problem {pid} submitted successfully!")
        st.session_state.solved_problems.add(pid)

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
            lang = st.selectbox("Language", ["cpp", "python", "java"], index=0)
            if st.button("Generate & Submit Solution"):
                st.session_state.problem_history.append(pid)
                open_problem(pid)
                text = get_problem_statement(slug)
                solution = solve_with_gemini(pid, lang, text)
                st.code(solution, language=lang)
                submit_solution_and_paste(pid, lang, solution)
        else:
            st.error("❌ Invalid problem number.")
elif user_input:
    st.chat_message("assistant").write(model.generate_content(user_input).text)
