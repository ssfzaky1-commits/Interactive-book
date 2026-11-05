import streamlit as st
import fitz  # PyMuPDF
from google import genai
from google.genai import types
import json
import os
import time

st.set_page_config(page_title="مولد الكتب التفاعلية", page_icon="📖")

st.title("📖 موقع تحويل الكتب لتفاعلية (Gemini)")
st.write("ارفع كتابك (حتى لو سكانر)، والذكاء الاصطناعي هيقرأ الصفحات ويحولها لأسئلة تفاعلية تلقائياً.")

# قراءة المفتاح من الإعدادات السرية
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("⚠️ مفتاح API غير موجود. تأكد من إضافته في إعدادات Secrets.")
    st.stop()

# إعداد عميل جوجل
client = genai.Client(api_key=api_key)

uploaded_file = st.file_uploader("ارفع ملف PDF", type="pdf")
max_pages = st.number_input("عدد الصفحات اللي عايز الذكاء الاصطناعي يحللها", min_value=1, max_value=50, value=5)

def clean_json_response(text):
    text = text.strip()
    if text.startswith("```json"): text = text[7:]
    if text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    return text.strip()

if uploaded_file:
    if st.button("🚀 ابدأ التحويل الذكي"):
        try:
            # حفظ الملف مؤقتاً
            with open("temp.pdf", "wb") as f:
                f.write(uploaded_file.read())
            
            doc = fitz.open("temp.pdf")
            total_pages = len(doc)
            pages_to_process = min(total_pages, max_pages)
            
            st.info(f"جاري تحليل {pages_to_process} صفحة... (الكتاب سكانر، ممكن ياخد وقت أطول شوية).")
            progress_bar = st.progress(0)
            annotations = {}
            
            for i in range(pages_to_process):
                page = doc[i]
                
                # تحويل الصفحة لصورة عشان الذكاء الاصطناعي يقراها
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)) # دقة مناسبة
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
                
                # قائمة بالموديلات البديلة في حالة الضغط
                models_to_try = ['gemini-3.8-flash', 'gemini-2.5-flash', 'gemini-2.0-flash']
                success = False
                
                for model_name in models_to_try:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=[
                                types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'),
                                prompt_text
                            ]
                        )
                        
                        content = response.text
                        clean_content = clean_json_response(content)
                        result = json.loads(clean_content)
                        annotations[i+1] = result.get("elements", [])
                        success = True
                        break # نجح، نخرج من حلقة الموديلات ونكمل للصفحة اللي بعدها
                        
                    except Exception as ai_err:
                        # لو الخطأ 503 (ضغط عالي) أو 429 (تجاوز حد)، نستنى شوية ونجرب موديل تاني
                        if "503" in str(ai_err) or "429" in str(ai_err):
                            st.toast(f"⚠️ النموذج {model_name} مشغول، جاري تجربة نموذج آخر لصفحة {i+1}...")
                            time.sleep(2) # استنى ثانيتين قبل ما تجرب
                            continue
                        else:
                            st.warning(f"خطأ في الصفحة {i+1} مع {model_name}: {ai_err}")
                            break
                            
                if not success:
                    st.warning(f"❌ تعذر تحليل الصفحة {i+1} بعد تجربة كل النماذج المتاحة.")
                
                progress_bar.progress((i + 1) / pages_to_process)
            
            # توليد كود الـ HTML
            html_content = f"""
            <!DOCTYPE html>
            <html dir="rtl"><head><meta charset="utf-8"><title>الكتاب التفاعلي</title>
            <style>
                body {{ font-family: system-ui, sans-serif; padding: 20px; background: #f0f2f5; max-width: 800px; margin: auto; }}
                .page {{ background: #fff; padding: 20px; margin-bottom: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,.1); }}
                .q {{ margin-bottom: 15px; padding: 10px; border-right: 4px solid #2563eb; background: #f8fafc; }}
                .q h4 {{ margin: 0 0 10px 0; }}
                label {{ display: block; margin-bottom: 5px; cursor: pointer; }}
                input[type="text"] {{ width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }}
            </style></head><body>
            <h1>📖 الكتاب التفاعلي</h1>
            <div id="app"></div>
            <script>
                const data = {json.dumps(annotations, ensure_ascii=False)};
                const app = document.getElementById('app');
                for (const page in data) {{
                    const pageDiv = document.createElement('div');
                    pageDiv.className = 'page';
                    pageDiv.innerHTML = `<h3>تفاعلات الصفحة ${{page}}</h3>`;
                    data[page].forEach((el, i) => {{
                        const qDiv = document.createElement('div');
                        qDiv.className = 'q';
                        qDiv.innerHTML = `<h4>${{el.question}}</h4>`;
                        if(el.type === 'choice') {{
                            el.options.forEach((opt, idx) => {{
                                qDiv.innerHTML += `<label><input type="radio" name="p${{page}}_q${{i}}"> ${{opt}}</label>`;
                            }});
                        }} else {{
                            qDiv.innerHTML += `<input type="text" placeholder="اكتب هنا...">`;
                        }}
                        pageDiv.appendChild(qDiv);
                    }});
                    app.appendChild(pageDiv);
                }}
            </script>
            </body></html>
            """
            
            st.success("✅ تم تجهيز الكتاب التفاعلي بنجاح!")
            st.download_button(
                label="⬇️ تحميل الكتاب (HTML)",
                data=html_content,
                file_name="interactive_book.html",
                mime="text/html"
            )
            
            # مسح الملف المؤقت
            os.remove("temp.pdf")
            
        except Exception as e:
            st.error(f"حدث خطأ: {str(e)}")
