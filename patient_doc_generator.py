import streamlit as st
from google import genai
from google.genai import types as genai_types # Using alias as in your example
import json
import re
from io import BytesIO
from docxtpl import DocxTemplate
import os

# --- Gemini API Function (adapted from YOUR example) ---
def get_structured_data_from_gemini(api_key: str, user_input_text: str) -> dict:
    """
    Processes natural language patient info using Gemini API (google-genai SDK)
    and returns structured data. Uses the client and streaming method from your example.
    """
    try:
        # The API key is now passed directly to the client, not configured globally first
        # genai.configure(api_key=api_key) # This is not needed if client takes api_key
        pass
    except Exception as e:
        st.error(f"Error during initial genai setup (if any): {e}")
        # return {"error": "API configuration failed", "details": str(e)} # No explicit configure step here

    client = genai.Client(api_key=api_key)

    # Model from your example
    model_name = "gemini-2.5-flash-preview-05-20" # Using a generally available model.
                                          # If "gemini-2.5-flash-preview-05-20" is specifically needed and available, use that.
                                          # The user's example had "gemini-2.5-flash-preview-05-20"
                                          # Let's try to use the user's specified model, but have a fallback.
    try:
        model_to_use = genai.get_model(f"models/{model_name}") # Check if model exists
    except Exception:
        st.warning(f"Model 'models/{model_name}' not found or accessible. Trying 'gemini-1.5-flash-latest'.")
        model_name = "gemini-1.5-flash-latest" # Fallback

    # Contents structure from your example
    contents = [
        genai_types.Content(
            role="user",
            parts=[
                genai_types.Part.from_text(text="""היי שלום אני ידידיה בדיוק הייתי במילואים מלא זמן, אני בן 40 ויש לי כאבים בעיניים, יוצאת לי מוגלה מסוימת, וקשה לי. ראיתי רופא עיניים, הביא לי איזה משהו. אה ויש לי גם כאבי בטן."""),
            ],
        ),
        genai_types.Content(
            role="model",
            parts=[
                genai_types.Part.from_text(text="""```json
{
  "name": "ידידיה",
  "age": 40,
  "kupat_cholim": "",
  "symptoms": "כאבים בעיניים, מוגלה מהעיניים, קושי בראייה, כאבי בטן.",
  "ai_recommondation": "מומלץ לחזור לרופא העיניים אם התסמינים בעיניים לא חלפו או החמירו, ולדווח על כאבי הבטן. ייתכן שיהיה צורך בבדיקה נוספת או הפניה לרופא גסטרואנטרולוג."
}
```"""),
            ],
        ),
        genai_types.Content( # This is where the actual user input goes
            role="user",
            parts=[
                genai_types.Part.from_text(text=user_input_text), # Replaced "INSERT_INPUT_HERE"
            ],
        ),
    ]

    # GenerateContentConfig from your example
    generate_content_config = genai_types.GenerateContentConfig(
        temperature=0,
        # thinking_config = genai_types.ThinkingConfig( # This might require specific model versions or features
        #     thinking_budget=0,
        # ),
        response_mime_type="text/plain", # Gemini will output JSON within this plain text
        # System instruction is now part of the model initialization or a specific parameter in generate_content
        # In the new google-genai, system_instruction is often part of the model object itself.
        # Let's try to pass it to generate_content if the client.models... structure supports it directly,
        # or initialize the model with it.
        # The example `client.models.generate_content_stream` does not show system_instruction in its config.
        # It's usually part of `genai.GenerativeModel(model_name, system_instruction=...)`
        # However, your example uses `client.models.generate_content_stream` which is a lower-level API.
        # Let's add the system prompt as the first "system" role message in `contents` if that's the convention for this client.
        # Or, more aligned with your example, the system prompt is part of `generate_content_config`.
    )

    # System instruction from your example
    system_instruction_parts = [
            genai_types.Part.from_text(text="""this is the system prompt. act as a patient info analuzer
analyze the attached user input, and return a json with the relevant fields. always return the fierlds. if the fiels is empty, just retirn it empty.

json:
name
age
kupat_cholim: like מכבי or כללית etc
symptoms
ai_recommondation:

here is the user input:"""),
        ]
    # For client.models.generate_content_stream, system_instruction is part of the config
    generate_content_config.system_instruction = genai_types.Content(parts=system_instruction_parts, role="system")


    full_response_text = ""
    json_string = ""
    try:
        # Using client.models.generate_content_stream as per your example
        stream = client.generate_content_stream( # Corrected method name
            model=f"models/{model_name}", # Model name needs "models/" prefix for client API
            contents=contents,
            generation_config=generate_content_config,
        )
        for chunk in stream:
            if chunk.text: # Ensure text exists
                 full_response_text += chunk.text

        # Extract JSON from the response text
        # The JSON might be wrapped in ```json ... ``` or be plain.
        match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", full_response_text, re.DOTALL)
        if match:
            json_string = match.group(1)
        else:
            # If not wrapped, assume the whole response is the JSON string (or attempt to find it)
            json_string = full_response_text.strip()
            # Basic check if it looks like JSON before parsing
            if not (json_string.startswith("{") and json_string.endswith("}")):
                # Try to find a JSON object within the text if it's not clean
                st.warning(f"Raw response from Gemini was not clean JSON. Attempting to find JSON object. Raw: '{json_string[:500]}...'")
                json_match_inner = re.search(r"(\{[\s\S]*?\})", json_string)
                if json_match_inner:
                    json_string = json_match_inner.group(1)
                else:
                    raise ValueError(f"Could not extract a valid JSON object from the response. Raw: {full_response_text}")


        if not json_string:
             raise ValueError(f"Extracted JSON string is empty. Raw response: {full_response_text}")

        data = json.loads(json_string)
        expected_keys = ["name", "age", "kupat_cholim", "symptoms", "ai_recommondation"]
        for key in expected_keys:
            if key not in data:
                data[key] = "" if key != "age" else None
        return data

    except json.JSONDecodeError as e:
        error_msg = f"JSON Decode Error: {e}. Attempted to parse: '{json_string or full_response_text}'"
        st.error(error_msg)
        return {"error": "Failed to parse JSON from Gemini", "details": error_msg, "name": "", "age": None, "kupat_cholim": "", "symptoms": "", "ai_recommondation": ""}
    except ValueError as e:
        error_msg = f"Data Extraction Error: {e}."
        st.error(error_msg)
        return {"error": "Failed to extract data from Gemini", "details": error_msg, "name": "", "age": None, "kupat_cholim": "", "symptoms": "", "ai_recommondation": ""}
    except Exception as e:
        # Check for prompt feedback if available in the stream or response object
        # (This might be more complex with the streaming client API)
        # if hasattr(stream, 'prompt_feedback') and stream.prompt_feedback:
        #     st.warning(f"Gemini Prompt Feedback: {stream.prompt_feedback}")
        error_msg = f"Gemini API call error: {type(e).__name__} - {e}"
        st.error(error_msg)
        return {"error": "Gemini API call failed", "details": error_msg, "name": "", "age": None, "kupat_cholim": "", "symptoms": "", "ai_recommondation": ""}


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
            st.rerun() # Use st.rerun() for cleaner state update
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

        with st.spinner("Processing with Gemini AI..."):
            # Pass the API key directly to the function
            structured_data = get_structured_data_from_gemini(gemini_api_key, patient_info_natural)

        if structured_data and "error" not in structured_data:
            st.subheader("2. Structured Patient Data (from Gemini)")
            st.json(structured_data) # Display the structured data

            st.subheader("3. Generate and Download DOCX")
            template_file = "patient_template.docx"

            if not os.path.exists(template_file):
                st.error(f"Error: DOCX template file '{template_file}' not found.")
                st.info(f"Please create a '{template_file}' in the same directory as this script. Use placeholders like {{{{name}}}}, {{{{age}}}}, etc.")
                st.stop()

            try:
                doc = DocxTemplate(template_file)
                context = {
                    "name": structured_data.get("name", ""),
                    "age": structured_data.get("age", ""),
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
    main()
