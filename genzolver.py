import streamlit as st
import requests
import time
import google.generativeai as genai
from bs4 import BeautifulSoup
import os
import pyperclip

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
os.system("apt-get update")
os.system("apt-get install -y wget unzip")
os.system("wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb")
os.system("dpkg -i google-chrome-stable_current_amd64.deb || true")
os.system("apt-get install -f -y")

# Install ChromeDriver
os.system("wget https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip")
os.system("unzip chromedriver_linux64.zip")
os.system("mv chromedriver /usr/bin/chromedriver")
os.system("chmod +x /usr/bin/chromedriver")

# --- 🔐 API Key Setup ---
API_KEY = os.getenv("GEMINI_API_KEY")  # Load API Key from Environment Variable
if not API_KEY:
    st.error("❌ API Key not found! Set 'GEMINI_API_KEY' environment variable.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# --- 🌐 Streamlit UI Setup ---
st.title("🤖 LeetCode Auto-Solver & Submission Bot")
st.write("Type 'Solve LeetCode [problem number]' or ask me anything!")

# --- 🗂 Cache LeetCode Problems ---
@st.cache_data
def fetch_problems():
    """Fetch all LeetCode problems"""
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

# --- 🚀 Automate LeetCode Execution ---
def automate_submission(pid, lang, solution):
    """Automate opening, pasting, running, and submitting the solution"""
    try:
        slug = get_slug(pid)
        if not slug:
            st.error("❌ Invalid problem number.")
            return
        
        url = f"https://leetcode.com/problems/{slug}/"
        st.info(f"🌍 Opening {url}...")
        
        # Setup Selenium WebDriver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Run in headless mode
        options.add_argument("--no-sandbox")  # Bypass OS-level sandbox
        options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
        options.add_argument("--disable-gpu")  # Disable GPU usage
        options.add_argument("--window-size=1920,1080")  # Set window size

# Install the driver and launch browser
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        driver.get(url)

        # Wait for the page to load
        time.sleep(5)

        # Click the "Sign In" button (if needed)
        try:
            sign_in_button = driver.find_element(By.XPATH, "//a[text()='Sign in']")
            sign_in_button.click()
            st.info("🔑 Please log in manually (waiting 15 sec)...")
            time.sleep(15)  # Wait for user to log in
        except:
            st.info("✅ Already logged in!")

        # Click "Editor" tab
        try:
            driver.find_element(By.XPATH, "//span[contains(text(),'Editor')]").click()
            time.sleep(2)
        except:
            st.warning("⚠ Couldn't find Editor tab, trying default.")

        # Select Language
        try:
            lang_dropdown = driver.find_element(By.XPATH, "//div[@role='combobox']")
            lang_dropdown.click()
            time.sleep(1)
            lang_option = driver.find_element(By.XPATH, f"//div[text()='{lang.capitalize()}']")
            lang_option.click()
            time.sleep(2)
        except:
            st.warning("⚠ Couldn't change language!")

        # Paste solution
        st.info("⌨ Pasting solution...")
        pyperclip.copy(solution)
        editor = driver.find_element(By.CLASS_NAME, "CodeMirror")
        editor.click()
        editor.send_keys(Keys.CONTROL, "a")  # Select all
        editor.send_keys(Keys.CONTROL, "v")  # Paste

        # Run the code
        st.info("🚀 Running solution...")
        run_button = driver.find_element(By.XPATH, "//button/span[contains(text(),'Run')]")
        run_button.click()
        time.sleep(10)  # Wait for execution

        # Submit the code
        st.info("🏆 Submitting solution...")
        submit_button = driver.find_element(By.XPATH, "//button/span[contains(text(),'Submit')]")
        submit_button.click()
        time.sleep(15)  # Wait for submission

        st.success("✅ Solution submitted successfully!")

        # Close the browser
        driver.quit()
    except Exception as e:
        st.error(f"❌ Selenium Error: {e}")

# --- 🎯 User Input Handling ---
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
