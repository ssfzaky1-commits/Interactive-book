import streamlit as st
import fitz  # PyMuPDF
from google import genai
from google.genai import types
import json
import os
import time

st.set_page_config(page_title="مستخرج بيانات الكتب", page_icon="📖")

st.title("📖 مستخرج البيانات (JSON)")
st.write("ارفع الكتاب، اختار نطاق الصفحات، ونزّل ملف البيانات عشان تدمجه بعدين على جهازك.")

api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("⚠️ مفتاح API غير موجود.")
    st.stop()

client = genai.Client(api_key=api_key)

uploaded_file = st.file_uploader("ارفع ملف PDF", type="pdf")

col1, col2 = st.columns(2)
with col1:
    start_page = st.number_input("من صفحة رقم", min_value=1, value=1)
with col2:
    end_page = st.number_input("إلى صفحة رقم", min_value=1, value=50)

def clean_json_response(text):
    text = text.strip()
    if text.startswith("```json"): text = text[7:]
    if text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    return text.strip()

if uploaded_file:
    if st.button("🚀 استخراج البيانات (JSON)"):
        try:
            with open("temp.pdf", "wb") as f:
                f.write(uploaded_file.read())
            
            doc = fitz.open("temp.pdf")
            total_pages = len(doc)
            
            if start_page > total_pages:
                st.error(f"الملف فيه {total_pages} صفحة بس!")
                st.stop()
            
            actual_end_page = min(end_page, total_pages)
            pages_count = actual_end_page - start_page + 1
            
            st.info(f"جاري تحليل الصفحات من {start_page} إلى {actual_end_page}...")
            progress_bar = st.progress(0)
            annotations = {}
            current_iteration = 0
            
            for i in range(start_page - 1, actual_end_page):
                page = doc[i]
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                img_bytes = pix.tobytes("jpeg")
                
                prompt_text = """
                هذه صورة لصفحة من كتاب.
                1. استخرج النص المكتوب في الصورة.
                2. بناءً على النص، صمم عناصر تفاعلية (أسئلة اختيار من متعدد أو حقول إجابة).
                
                أرجع النتيجة بصيغة JSON فقط (بدون أي كلام إضافي) بهذا الشكل:
                {
                    "elements": [
                        {"type": "choice", "question": "السؤال هنا؟", "options": ["أ", "ب", "ج"], "correct": 0},
                        {"type": "text", "question": "اكتب إجابتك هنا", "answer": "الإجابة المتوقعة"}
                    ]
                }
                """
                
                models_to_try = ['gemini-3.8-flash', 'gemini-2.5-flash', 'gemini-2.0-flash']
                success = False
                
                for model_name in models_to_try:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=[types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'), prompt_text]
                        )
                        content = response.text
                        clean_content = clean_json_response(content)
                        result = json.loads(clean_content)
                        annotations[i+1] = result.get("elements", [])
                        success = True
                        break
                    except Exception as ai_err:
                        if "503" in str(ai_err) or "429" in str(ai_err):
                            time.sleep(2)
                            continue
                        else:
                            break
                            
                if not success:
                    st.warning(f"❌ تعذر تحليل الصفحة {i+1}.")
                
                current_iteration += 1
                progress_bar.progress(current_iteration / pages_count)
                time.sleep(1) # استراحة بسيطة
            
            st.success(f"✅ تم استخراج بيانات الصفحات من {start_page} إلى {actual_end_page}!")
            st.download_button(
                label="⬇️ تحميل ملف البيانات (JSON)",
                data=json.dumps(annotations, ensure_ascii=False, indent=2),
                file_name=f"data_{start_page}_to_{actual_end_page}.json",
                mime="application/json"
            )
            os.remove("temp.pdf")
        except Exception as e:
            st.error(f"حدث خطأ: {str(e)}")
