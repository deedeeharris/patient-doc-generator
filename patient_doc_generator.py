import streamlit as st
from google import genai
from google.genai import types as genai_types
import json
import re # Still useful for safety, though less critical with application/json
from io import BytesIO
from docxtpl import DocxTemplate
import os

# --- Gemini API Function (corrected to match YOUR LATEST example) ---
def get_structured_data_from_gemini(api_key: str, user_input_text: str) -> dict:
    """
    Processes natural language patient info using Gemini API (google-genai SDK)
    and returns structured data. Uses the client.models.generate_content_stream method.
    """
    client = genai.Client(api_key=api_key)

    # Model from your LATEST example
    model_name = "gemini-2.5-flash-preview-05-20"

    # Contents structure from your example
    # The first user/model pair is for few-shot prompting
    contents = [
        genai_types.Content(
            role="user",
            parts=[
                # Using the example text you provided for the few-shot prompt
                genai_types.Part.from_text(text="""היי אני ידידיה זהו דוגמא בלבד, כשממיר את הקוד לפונקציה תשאיר את זה עם משתנה, ככה זה יימשך מתוך הצד לקוח

ידידיה בן 40 חולה"""),
            ],
        ),
        genai_types.Content(
            role="model",
            parts=[
                # Using the example JSON output you provided for the few-shot prompt
                genai_types.Part.from_text(text="""{
  "name": "ידידיה",
  "age": "40",
  "kupat_cholim": "",
  "symptoms": "חולה",
  "ai_recommondation": ""
}"""),
            ],
        ),
        genai_types.Content( # This is where the actual user input goes
            role="user",
            parts=[
                genai_types.Part.from_text(text=user_input_text), # Actual patient input
            ],
        ),
    ]

    # GenerateContentConfig from your LATEST example
    generate_content_config = genai_types.GenerateContentConfig(
        temperature=0,
        thinking_config = genai_types.ThinkingConfig( # Included as per your example
            thinking_budget=0,
        ),
        response_mime_type="application/json", # Crucial change!
        system_instruction=[ # System instruction as a list of Parts
            genai_types.Part.from_text(text="""system prompt here
this is the system prompt. act as a patient info analuzer
analyze the attached user input, and return a json with the relevant fields. always return the fierlds. if the fiels is empty, just retirn it empty.

json:
name
age
kupat_cholim: like מכבי or כללית etc
symptoms
ai_recommondation:

here is the user input:"""),
        ],
    )

    full_response_text = ""
    try:
        # Using client.models.generate_content_stream as per your LATEST example
        # The model name is passed directly, without the "models/" prefix here.
        stream = client.models.generate_content_stream(
            model=model_name, # e.g., "gemini-2.5-flash-preview-05-20"
            contents=contents,
            generation_config=generate_content_config,
        )
        for chunk in stream:
            if chunk.text:
                 full_response_text += chunk.text
        
        # Since response_mime_type="application/json", full_response_text should be a JSON string
        if not full_response_text.strip():
            raise ValueError("Received empty response from Gemini API.")

        data = json.loads(full_response_text)
        
        # Ensure all expected keys are present, defaulting to empty strings or None
        expected_keys = ["name", "age", "kupat_cholim", "symptoms", "ai_recommondation"]
        for key in expected_keys:
            if key not in data:
                # Convert age to string if it's a number, as per your example output
                if key == "age" and data.get(key) is not None:
                    data[key] = str(data[key])
                elif key == "age": # if age is missing or None
                    data[key] = "" # Default to empty string for template
                else:
                    data[key] = data.get(key, "") # Use get for other keys, default to ""
        
        # Ensure age is a string for consistency with your example output
        if "age" in data and data["age"] is not None:
            data["age"] = str(data["age"])
        elif "age" not in data or data.get("age") is None : # if age is missing or None
             data["age"] = ""


        return data

    except json.JSONDecodeError as e:
        error_msg = f"JSON Decode Error: {e}. Gemini response: '{full_response_text}'"
        st.error(error_msg)
        return {"error": "Failed to parse JSON from Gemini", "details": error_msg, "name": "", "age": "", "kupat_cholim": "", "symptoms": "", "ai_recommondation": ""}
    except ValueError as e: # Catching empty response
        error_msg = f"Value Error: {e}. Gemini response: '{full_response_text}'"
        st.error(error_msg)
        return {"error": "Invalid data from Gemini", "details": error_msg, "name": "", "age": "", "kupat_cholim": "", "symptoms": "", "ai_recommondation": ""}
    except Exception as e:
        error_msg = f"Gemini API call error: {type(e).__name__} - {e}. Model: {model_name}. Check if the model is available and the API key is correct."
        st.error(error_msg)
        # You might want to inspect `e.args` or other attributes of the exception for more details from the API
        if hasattr(e, 'response') and e.response:
            st.error(f"API Response details: {e.response}")
        return {"error": "Gemini API call failed", "details": error_msg, "name": "", "age": "", "kupat_cholim": "", "symptoms": "", "ai_recommondation": ""}


# --- Password Protection ---
def check_password():
    if "APP_PASSWORD" not in st.secrets:
        st.error("FATAL: APP_PASSWORD is not set in Streamlit secrets (.streamlit/secrets.toml).")
        st.stop()
        return False

    app_password = st.secrets["APP_PASSWORD"]

    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if st.session_state.password_correct:
        return True

    password_input = st.text_input("Enter Password to access the app:", type="password", key="password_field")

    if st.button("Login", key="login_button"):
        if password_input == app_password:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Password incorrect.")
            st.session_state.password_correct = False
    return False

# --- Main App ---
def main():
    st.set_page_config(page_title="Patient Doc Generator", layout="wide")
    st.title("📝 Patient Document Generator")

    if not check_password():
        st.stop()

    try:
        gemini_api_key = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error("GEMINI_API_KEY not found in st.secrets. Please set it in .streamlit/secrets.toml")
        st.stop()
        return

    st.subheader("1. Enter Patient Information (Natural Language)")
    patient_info_natural = st.text_area("Describe the patient's details, symptoms, history, etc.:", height=200, key="patient_input_area")

    if st.button("✨ Generate Structured Data & Document", key="generate_button"):
        if not patient_info_natural.strip():
            st.warning("Please enter some patient information.")
            st.stop()

        with st.spinner(f"Processing with Gemini AI (model: {get_structured_data_from_gemini.__defaults__[0] if get_structured_data_from_gemini.__defaults__ else 'gemini-2.5-flash-preview-05-20'})..."): # Shows model in spinner
            structured_data = get_structured_data_from_gemini(gemini_api_key, patient_info_natural)

        if structured_data and "error" not in structured_data:
            st.subheader("2. Structured Patient Data (from Gemini)")
            st.json(structured_data)

            st.subheader("3. Generate and Download DOCX")
            template_file = "patient_template.docx"

            if not os.path.exists(template_file):
                st.error(f"Error: DOCX template file '{template_file}' not found.")
                st.info(f"Please create a '{template_file}' in the same directory as this script. Use placeholders like {{{{name}}}}, {{{{age}}}}, etc.")
                st.stop()

            try:
                doc = DocxTemplate(template_file)
                # Ensure age is a string for the template, even if it was a number
                context = {
                    "name": structured_data.get("name", ""),
                    "age": str(structured_data.get("age", "")), # Ensure age is string
                    "kupat_cholim": structured_data.get("kupat_cholim", ""),
                    "symptoms": structured_data.get("symptoms", ""),
                    "ai_recommondation": structured_data.get("ai_recommondation", "")
                }
                doc.render(context)

                bio = BytesIO()
                doc.save(bio)
                bio.seek(0)

                doc_filename = f"{str(context.get('name', 'patient')).replace(' ', '_')}_document.docx"
                st.download_button(
                    label="📥 Download Patient Document (DOCX)",
                    data=bio,
                    file_name=doc_filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            except Exception as e:
                st.error(f"Error generating DOCX file: {e}")
                st.error(f"Data used for template: {context}")

        elif structured_data and "error" in structured_data:
            st.error(f"Could not process data: {structured_data.get('details', 'Unknown error')}")
        else:
            st.error("An unexpected error occurred while fetching data from Gemini.")

if __name__ == "__main__":
    # To make the model name in spinner work if __main__ is run directly (though not typical for streamlit)
    # This is a bit of a hack for the spinner text if run directly.
    # In Streamlit, the function will be called from main().
    if not get_structured_data_from_gemini.__defaults__:
         get_structured_data_from_gemini.__defaults__ = ("gemini-2.5-flash-preview-05-20",)
    main()
