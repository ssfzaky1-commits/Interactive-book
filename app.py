import streamlit as st
import fitz  # PyMuPDF
from google import genai
from google.genai import types
import json
import os
import time

st.set_page_config(page_title="مستخرج بيانات الكتب", page_icon="📖")

st.title("📖 مستخرج البيانات (JSON)")
st.write("ارفع الكتاب، اختار نطاق الصفحات، ونزّل ملف البيانات.")

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

# دالة ذكية لإرسال الطلب وإعادة المحاولة عند الازدحام
def generate_with_retry(img_bytes, prompt_text, max_retries=5):
    # النماذج المتاحة
    models = ['gemini-3.8-flash', 'gemini-2.5-flash']
    
    for attempt in range(max_retries):
        for model_name in models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'),
                        prompt_text
                    ]
                )
                return response.text # نجحنا، نرجع النتيجة فوراً
            except Exception as e:
                error_str = str(e)
                # لو السيرفر مشغول (503) أو تعدينا الحد (429)، نستنى ونحاول تاني
                if "503" in error_str or "429" in error_str or "UNAVAILABLE" in error_str:
                    continue # جرب الموديل اللي بعده
                else:
                    # لو خطأ تاني (زي مفتاح غلط أو صورة مش مقروءة)، نرمي الخطأ
                    raise e
        
        # لو كل الموديلات فشلت في المحاولة دي، نستنى وقت أطول (Exponential Backoff)
        wait_time = 2 ** attempt # 1, 2, 4, 8, 16 ثانية
        st.toast(f"⚠️ السيرفر مزدحم، جاري إعادة المحاولة بعد {wait_time} ثانية...")
        time.sleep(wait_time)
    
    raise Exception("فشل الاتصال بالذكاء الاصطناعي بعد كل المحاولات.")

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
                
                try:
                    # استخدام الدالة الذكية اللي بتعيد المحاولة
                    raw_content = generate_with_retry(img_bytes, prompt_text)
                    clean_content = clean_json_response(raw_content)
                    result = json.loads(clean_content)
                    annotations[i+1] = result.get("elements", [])
                except Exception as ai_err:
                    st.warning(f"❌ تعذر تحليل الصفحة {i+1}: {ai_err}")
                
                current_iteration += 1
                progress_bar.progress(current_iteration / pages_count)
                time.sleep(1) # استراحة بسيطة بين الصفحات
            
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
