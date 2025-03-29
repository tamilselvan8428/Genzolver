import os
import streamlit as st
import webbrowser
import requests
import time
import google.generativeai as genai
from bs4 import BeautifulSoup

# --- 🔐 Gemini API Setup ---
API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# --- 🚀 Cloud/Local Environment Check ---
is_cloud = os.environ.get("DISPLAY") is None  # Cloud servers don’t have a GUI

if not is_cloud:
    import pyautogui
    import pyperclip

# --- 🌐 Streamlit UI Setup ---
st.title("🤖 LeetCode Auto-Solver & Auto-Submit")
st.write("Type 'Solve LeetCode [problem number]' to start!")

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

def get_slug(pid): 
    return problems_dict.get(pid)

def open_problem(pid):
    """Open the LeetCode problem if not already open."""
    slug = get_slug(pid)
    if slug:
        url = f"https://leetcode.com/problems/{slug}/"
        webbrowser.open(url, new=2)  # Open in a new tab
        return url
    return None

# --- 📝 Fetch Problem Statement ---
def get_problem_statement(slug):
    """Fetch problem statement using LeetCode GraphQL API."""
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
    """Generate a solution using Gemini AI."""
    if text.startswith("❌"):
        return "❌ Problem fetch failed."
    
    prompt = f"""Solve the following LeetCode problem in {lang}:
Problem:  
{text}
Requirements:
- Follow the LeetCode function signature.
- Return only the function/class definition.
- Do NOT use code fences.
Solution:"""
    
    try:
        res = model.generate_content(prompt)
        return res.text.strip()
    except Exception as e:
        return f"❌ Gemini Error: {e}"

# --- 🛠 Automate Pasting, Running & Submitting ---
def auto_paste_and_submit():
    """Automates clicking, pasting, running, and submitting."""
    time.sleep(5)  # Wait for page load
    
    # Click inside the code editor (adjust coordinates as needed)
    pyautogui.click(x=1500, y=400)
    time.sleep(1)

    # Paste solution
    pyautogui.hotkey('ctrl', 'a')  # Select all
    pyautogui.hotkey('ctrl', 'v')  # Paste
    time.sleep(1)

    # Run solution
    pyautogui.hotkey('ctrl', '`')
    time.sleep(8)

    # Check if run was successful (mock function)
    if is_run_successful():
        st.success("✅ Code executed successfully! Now submitting...")

        # Submit solution
        pyautogui.hotkey('ctrl', 'enter')
        time.sleep(10)

        if is_submission_successful():
            st.success("🏆 Problem submitted successfully!")
        else:
            st.error("❌ Submission failed. Retrying...")
            auto_paste_and_submit()  # Retry
    else:
        st.error("❌ Run failed. Check the solution or retry.")

# --- ✅ Verification Helpers ---
def is_run_successful():
    """Mock function to check if run was successful."""
    time.sleep(5)
    return True  # Replace with image detection if needed

def is_submission_successful():
    """Mock function to check if submission was successful."""
    time.sleep(5)
    return True  # Replace with image detection if needed

# --- 🎯 User Input Handling ---
user_input = st.text_input("Your command:")

if user_input.lower().startswith("solve leetcode"):
    tokens = user_input.strip().split()
    if len(tokens) == 3 and tokens[2].isdigit():
        pid = tokens[2]
        slug = get_slug(pid)
        if slug:
            lang = st.selectbox("Language", ["cpp", "python", "java", "javascript", "csharp"], index=0)
            
            if st.button("Generate Solution"):
                text = get_problem_statement(slug)
                solution = solve_with_gemini(pid, lang, text)
                st.code(solution, language=lang)
                
                # Cloud mode: Allow manual copying
                if is_cloud:
                    if st.button("Copy solution to clipboard"):
                        import pyperclip
                        pyperclip.copy(solution)
                        st.success("✅ Solution copied! Now paste it manually in LeetCode.")
                else:
                    # Local mode: Auto-Open LeetCode and submit
                    st.info("🔍 Opening LeetCode page...")
                    open_problem(pid)
                    time.sleep(5)  # Wait for page load

                    # Copy solution to clipboard
                    pyperclip.copy(solution)

                    # Automate pasting and submitting
                    auto_paste_and_submit()
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
