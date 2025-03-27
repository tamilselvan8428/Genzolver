import streamlit as st
import webbrowser
import requests
import time
import os
import json
import zipfile
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
def get_slug(pid): 
    return problems_dict.get(pid)

# --- 🛠 WebDriver Setup ---
# --- 🛠 WebDriver Setup ---
def setup_webdriver():
    if "webdriver_path" not in st.session_state:
        st.session_state["webdriver_path"] = "C:\\WebDrivers\\msedgedriver.exe"

    driver_path = st.session_state["webdriver_path"]

    if not os.path.exists(driver_path):
        st.warning("❌ Edge WebDriver not found!")
        new_path = st.text_input("Enter WebDriver Path:", driver_path)
        if st.button("Save Path"):
            st.session_state["webdriver_path"] = new_path
            st.success("✅ WebDriver path updated!")
            return new_path
        return None
    return driver_path

# --- 🌐 Open LeetCode Problem with Recovery ---
def open_problem(pid):
    slug = get_slug(pid)
    if not slug:
        st.error("❌ Invalid problem number.")
        return None

    url = f"https://leetcode.com/problems/{slug}/"
    st.info(f"🌐 Opening {url} in Edge...")

    driver_path = setup_webdriver()
    if not driver_path:
        return None

    options = EdgeOptions()
    options.use_chromium = True
    options.add_argument("--start-maximized")
    options.add_experimental_option("detach", True)

    try:
        driver = webdriver.Edge(service=EdgeService(driver_path), options=options)
        driver.get(url)
        return driver  # Return driver for later use

    except WebDriverException as e:
        st.error(f"❌ Edge could not open: {e}")

        # Recovery Options
        retry = st.button("🔄 Retry Opening Edge")
        switch_to_chrome = st.button("🌍 Switch to Chrome")

        if retry:
            return open_problem(pid)  # Retry opening Edge

        if switch_to_chrome:
            st.session_state["use_chrome"] = True
            return open_problem_chrome(pid)  # Switch to Chrome

    return None

# --- 🌍 Alternative: Open in Chrome ---
def open_problem_chrome(pid):
    slug = get_slug(pid)
    if not slug:
        st.error("❌ Invalid problem number.")
        return None

    url = f"https://leetcode.com/problems/{slug}/"
    st.info(f"🌍 Opening {url} in Chrome...")

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_experimental_option("detach", True)

    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        return driver
    except WebDriverException as e:
        st.error(f"❌ Chrome could not open: {e}")
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

# --- 🤖 Generate Solution with Gemini AI ---
def solve_with_gemini(pid, lang, text):
    if text.startswith("❌"):
        return "❌ Problem fetch failed."
    
    prompt = f"""Solve the following LeetCode problem in {lang}:
Problem:  
{text}
Requirements:
- Wrap the solution inside class Solution {{ public: ... }}.
- Follow the LeetCode function signature.
- Return only the full class definition with the method inside.
- Do NOT use code fences like  or {lang}.
Solution:"""
    
    try:
        res = model.generate_content(prompt)
        solution = res.text.strip()

        # Save solution in session state
        st.session_state.analytics[pid]["solutions"].append(solution)
        st.session_state.analytics[pid]["attempts"] += 1

        return solution
    except Exception as e:
        return f"❌ Gemini Error: {e}"

# --- 🎯 User Input Handling ---
user_input = st.text_input("Your command or question:")

if user_input.lower().startswith("solve leetcode"):
    tokens = user_input.strip().split()
    if len(tokens) == 3 and tokens[2].isdigit():
        pid = tokens[2]
        slug = get_slug(pid)
        if slug:
            lang = st.selectbox("Language", ["cpp", "python", "java", "javascript", "csharp"], index=0)
            if st.button("Generate Solution"):
                st.session_state.problem_history.append(pid)
                open_problem(pid)
                text = get_problem_statement(slug)
                solution = solve_with_gemini(pid, lang, text)
                st.code(solution, language=lang)
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

# --- 📊 Analytics Display ---
if st.button("Show Analytics"):
    st.write("### 📈 Problem Solving Analytics")
    for pid, data in st.session_state.analytics.items():
        st.write(f"Problem {pid}: Attempts: {data['attempts']}")
        for sol in data["solutions"]:
            st.code(sol, language="cpp")

# --- 🕘 History & ✅ Solved Problems ---
if st.session_state.problem_history:
    st.write("### 🕘 Recent Problems:")
    for pid in reversed(st.session_state.problem_history):
        st.write(f"- Problem {pid}")
if st.session_state.solved_problems:
    st.write("### ✅ Solved:")
    st.write(", ".join(sorted(st.session_state.solved_problems)))
