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

# --- 🔐 API Key from Streamlit Secrets ---
API_KEY = st.secrets["GEMINI_API_KEY"]
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
Solution:"""
    
    try:
        res = model.generate_content(prompt)
        solution = res.text.strip()
        
        # Save solution
        st.session_state.analytics[pid]["solutions"].append(solution)
        st.session_state.analytics[pid]["attempts"] += 1

        return solution
    except Exception as e:
        return f"❌ Gemini Error: {e}"

# --- 🛠 Auto Run & Submit Solution ---
def auto_run_submit(pid, lang, solution):
    if not solution or solution.startswith("❌"):
        st.error("❌ Solution not generated correctly.")
        return

    slug = get_slug(pid)
    if not slug:
        st.error("❌ Invalid problem number.")
        return
    
    url = f"https://leetcode.com/problems/{slug}/"
    st.info(f"🌍 Opening LeetCode Problem: {url}")

    # Set up Edge WebDriver
    try:
        options = webdriver.EdgeOptions()
        options.add_argument("start-maximized")
        driver = webdriver.Edge(executable_path="C:\\WebDrivers\\msedgedriver.exe", options=options)
        driver.get(url)
        options.add_argument("--headless")  # No GUI mode
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--remote-debugging-port=9222")


        # Wait for page to load
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "monaco-editor")))

        # Click on "Sign In" if required
        try:
            sign_in_button = driver.find_element(By.XPATH, "//a[contains(text(), 'Sign In')]")
            sign_in_button.click()
            st.warning("⚠️ Please sign in manually, then press Continue.")
            time.sleep(10)  # Give time for manual sign-in
        except:
            st.info("✅ Already signed in.")

        # Select language
        lang_selector = driver.find_element(By.CLASS_NAME, "language-selector")
        lang_selector.click()
        time.sleep(1)
        lang_option = driver.find_element(By.XPATH, f"//div[text()='{lang.capitalize()}']")
        lang_option.click()

        # Locate the code editor and paste the solution
        editor = driver.find_element(By.CLASS_NAME, "monaco-editor")
        editor.click()
        time.sleep(1)

        # Send keyboard shortcuts to select all and replace code
        editor.send_keys(Keys.CONTROL + "a")
        editor.send_keys(Keys.BACKSPACE)
        editor.send_keys(solution)

        # Click "Run" button
        run_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Run')]")
        run_button.click()
        st.info("🚀 Running the solution...")

        # Wait for run to complete
        time.sleep(10)  # Adjust if needed

        # Click "Submit" button
        submit_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Submit')]")
        submit_button.click()
        st.success(f"✅ Solution for Problem {pid} has been submitted successfully!")

        # Close browser
        time.sleep(5)
        driver.quit()

        # Add problem to solved list
        st.session_state.solved_problems.add(pid)

    except WebDriverException as e:
        st.error(f"❌ WebDriver Error: {e}")


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
                auto_run_submit(pid, lang, solution)
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
