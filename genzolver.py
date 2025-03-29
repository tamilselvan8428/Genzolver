import os
import time
import requests
import streamlit as st
import google.generativeai as genai
import pyperclip
import pyautogui
from bs4 import BeautifulSoup

# --- Start a Virtual Display (required for pyautogui in headless environments) ---
# This uses Xvfb; ensure it is installed in your environment.
os.system("Xvfb :1 -screen 0 1920x1080x24 &")
os.environ["DISPLAY"] = ":1"

# --- 🔐 API Key Setup ---
API_KEY = os.getenv("GEMINI_API_KEY")  # Set this in your environment
if not API_KEY:
    st.error("❌ API Key not found! Set 'GEMINI_API_KEY' environment variable.")
    st.stop()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# --- 🌐 Streamlit UI ---
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
    """Fetch problem statement from LeetCode using GraphQL API."""
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
    """Generate solution using Gemini AI."""
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

# --- 🚀 Automate LeetCode Execution using Keyboard Shortcuts ---
def automate_submission(pid, lang, solution):
    """
    Automates opening a LeetCode problem, pasting the solution, running it, and submitting it 
    by triggering keyboard shortcuts using pyautogui.
    """
    slug = get_slug(pid)
    if not slug:
        st.error("❌ Invalid problem number.")
        return

    url = f"https://leetcode.com/problems/{slug}/"
    st.info(f"🌍 Opening {url}...")

    # Step 1: Open a new tab in the browser (Ctrl + T)
    pyautogui.hotkey('ctrl', 't')
    time.sleep(1)

    # Step 2: Paste the URL and hit Enter
    pyperclip.copy(url)
    pyautogui.hotkey('ctrl', 'v')
    pyautogui.press('enter')
    time.sleep(5)  # Wait for the page to load

    # Step 3: (If needed) wait a bit for manual login; adjust delay as required
    time.sleep(3)

    # Step 4: Paste the solution into the code editor
    st.info("⌨ Pasting solution into editor...")
    pyperclip.copy(solution)
    pyautogui.hotkey('ctrl', 'a')  # Select all text in the editor
    pyautogui.hotkey('ctrl', 'v')  # Paste solution
    time.sleep(1)

    # Step 5: Run the code by triggering Ctrl + '
    st.info("🚀 Running solution...")
    pyautogui.hotkey('ctrl', "'")
    time.sleep(10)

    # Step 6: Submit the solution with Ctrl + Enter
    st.info("🏆 Submitting solution...")
    pyautogui.hotkey('ctrl', 'enter')
    time.sleep(15)

    st.success("✅ Solution submitted successfully!")

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
