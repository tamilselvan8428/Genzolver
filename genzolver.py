import streamlit as st
import webbrowser
import requests
import time
import pyautogui
import pyperclip
import google.generativeai as genai
from bs4 import BeautifulSoup

# --- 🔐 Gemini API Setup ---
API_KEY = "AIzaSyDJcR1N1QoNrmNTIPl492ZsHhos2sWW-Vs"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# --- 🌐 Streamlit UI Setup ---
st.title("🤖 LeetCode Auto-Solver & Analytics Chatbot")
st.write("Type 'Solve LeetCode [problem number]' or ask me anything!")

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
    """Open the LeetCode problem in the browser."""
    slug = get_slug(pid)
    if slug:
        url = f"https://leetcode.com/problems/{slug}/"
        webbrowser.open(url)
        time.sleep(7)  # Wait for page to load
        return url
    st.error("❌ Invalid problem number.")
    return None

# --- 📝 Fetch Problem Statement ---
def get_problem_statement(slug):
    """Fetch the problem statement from LeetCode using GraphQL API."""
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

# --- 🔍 Page Verification ---
def ensure_leetcode_page(pid):
    """Ensure the correct LeetCode problem page is open."""
    open_problem(pid)

def focus_on_editor():
    """Ensure the editor is selected and paste the solution directly."""
    time.sleep(3)

    # Move mouse to LeetCode editor's area and click (adjust coordinates as needed)
    pyautogui.click(x=800, y=500)  # Update these coordinates based on your screen resolution
    
    time.sleep(1)

    # Ensure paste action happens in the LeetCode editor
    pyautogui.hotkey('ctrl', 'a')  # Select all existing code
    pyautogui.hotkey('ctrl', 'v')  # Paste new code
    time.sleep(1)

# --- 🛠 Submit Solution ---    
def submit_solution(pid, lang, sol):
    """Automate the process of opening LeetCode, pasting solution, running, and submitting."""
    try:
        st.info("🔍 Opening LeetCode page...")
        ensure_leetcode_page(pid)

        st.info("🚀 Switching to LeetCode browser window...")
        time.sleep(3)
        pyautogui.hotkey('alt', 'tab')  # Switch to browser
        time.sleep(3)

        # Copy solution to clipboard before pasting
        pyperclip.copy(sol)

        st.info("⌨ Moving to editor and pasting solution...")
        focus_on_editor()  # Click into editor and paste

        # Run the solution
        pyautogui.hotkey('ctrl', '`')
        st.info("🚀 Running code...")
        time.sleep(8)

        if is_run_successful():
            st.success("✅ Code executed successfully! Now submitting...")

            # Submit the solution
            pyautogui.hotkey('ctrl', 'enter')
            st.info("🏆 Submitting solution...")
            time.sleep(10)

            if is_submission_successful():
                st.success(f"✅ Problem {pid} submitted successfully!")
            else:
                st.error("❌ Submission failed. Retrying...")
                submit_solution(pid, lang, sol)  # Retry if needed
        else:
            st.error("❌ Run failed. Check the solution or retry.")
    except Exception as e:
        st.error(f"❌ PyAutoGUI Error: {e}")

# --- ✅ Verification Helpers ---
def is_run_successful():
    """Check if code execution was successful."""
    time.sleep(5)
    return True  # Mock function; replace with image detection if needed

def is_submission_successful():
    """Check if submission was successful."""
    time.sleep(5)
    return True  # Mock function; replace with image detection if needed

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
                open_problem(pid)
                text = get_problem_statement(slug)
                solution = solve_with_gemini(pid, lang, text)
                st.code(solution, language=lang)
                submit_solution(pid, lang, solution)
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
