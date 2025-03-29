import os
import time
import requests
import streamlit as st
import google.generativeai as genai
import pyperclip
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup

# ✅ Setup Headless Browser for Cloud Deployment
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"
GOOGLE_CHROME_PATH = "/usr/bin/google-chrome-stable"

# ✅ Set API Key for Gemini AI
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    st.error("❌ API Key not found! Set 'GEMINI_API_KEY' environment variable.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# ✅ Streamlit UI
st.title("🤖 LeetCode Auto-Solver & Submission Bot")
st.write("Type 'Solve LeetCode [problem number]' to get a solution!")

@st.cache_data
def fetch_problems():
    """Fetch all LeetCode problems."""
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

def get_slug(pid): 
    return problems_dict.get(pid)

def get_problem_statement(slug):
    """Fetch problem statement from LeetCode using GraphQL API"""
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

def solve_with_gemini(pid, lang, text):
    """Generate solution using Gemini AI"""
    if text.startswith("❌"):
        return "❌ Problem fetch failed."
    
    prompt = f"""Solve the following LeetCode problem in {lang}:
Problem:  
{text}
Requirements:
- Wrap the solution inside class Solution {{ public: ... }}.
- Follow the LeetCode function signature.
- Return only the full class definition with the method inside.
- Do NOT use code fences.
Solution:"""
    
    try:
        res = model.generate_content(prompt)
        return res.text.strip()
    except Exception as e:
        return f"❌ Gemini Error: {e}"

def automate_submission(pid, lang, solution):
    """Automates opening a LeetCode problem, pasting a solution, running, and submitting it."""
    slug = get_slug(pid)
    if not slug:
        st.error("❌ Invalid problem number.")
        return

    url = f"https://leetcode.com/problems/{slug}/"
    st.info(f"🌍 Opening {url}...")

    # ✅ Setup Chrome options for headless mode
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run without UI
    options.add_argument("--no-sandbox")  # Required for cloud servers
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.binary_location = GOOGLE_CHROME_PATH  # Ensure correct binary

    # ✅ Initialize WebDriver
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)
    time.sleep(5)

    try:
        # Find and click the code editor
        editor = driver.find_element(By.CLASS_NAME, "monaco-editor")
        editor.click()
        time.sleep(1)
        editor.send_keys(Keys.CONTROL, "a")  # Select all
        editor.send_keys(solution)  # Paste solution
    except Exception as e:
        st.error(f"❌ Error pasting solution: {e}")

    # Click 'Run'
    try:
        run_button = driver.find_element(By.XPATH, "//button[contains(text(),'Run')]")
        run_button.click()
        st.info("🚀 Running solution...")
        time.sleep(10)
    except Exception as e:
        st.error(f"❌ Error clicking Run: {e}")

    # Click 'Submit'
    try:
        submit_button = driver.find_element(By.XPATH, "//button[contains(text(),'Submit')]")
        submit_button.click()
        st.success("✅ Solution submitted successfully!")
        time.sleep(15)
    except Exception as e:
        st.error(f"❌ Error clicking Submit: {e}")

    driver.quit()

# ✅ Handle User Commands
user_input = st.text_input("Your command or question:")

if user_input.lower().startswith("solve leetcode"):
    tokens = user_input.strip().split()
    if len(tokens) == 3 and tokens[2].isdigit():
        pid = tokens[2]
        slug = get_slug(pid)
        if slug:
            lang = st.selectbox("Language", ["Python", "C++", "Java", "JavaScript", "C#"], index=0)
            if st.button("Generate & Submit Solution"):
                text = get_problem_statement(slug)
                solution = solve_with_gemini(pid, lang.lower(), text)
                st.code(solution, language=lang.lower())
                automate_submission(pid, lang.lower(), solution)
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
