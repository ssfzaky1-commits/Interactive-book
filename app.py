import streamlit as st
import fitz  # PyMuPDF
from groq import Groq
import json
import os

st.set_page_config(page_title="مولد الكتب التفاعلية", page_icon="📖", layout="wide")

st.title("📖 موقع تحويل الكتب لتفاعلية (بالذكاء الاصطناعي)")
st.write("ارفع أي كتاب PDF، والذكاء الاصطناعي هيقرأه ويحطلك الأسئلة والتفاعلات تلقائياً.")

# المفتاح السري (ممكن المستخدم يدخله لو حب)
api_key = st.text_input("أدخل مفتاح Groq API (اللي جبته من موقعهم):", type="password")

uploaded_file = st.file_uploader("ارفع الكتاب (PDF)", type="pdf")
max_pages = st.number_input("عدد الصفحات اللي عايز تحولها (الذكاء الاصطناعي بياخد وقت، ابدأ بـ 10 صفحات للتجربة)", min_value=1, max_value=100, value=10)

if uploaded_file and api_key:
    if st.button("🚀 ابدأ التحويل الذكي"):
        try:
            client = Groq(api_key=api_key)
            
            with open("temp.pdf", "wb") as f:
                f.write(uploaded_file.read())
            
            doc = fitz.open("temp.pdf")
            total_pages = len(doc)
            pages_to_process = min(total_pages, max_pages)
            
            st.info(f"جاري تحليل {pages_to_process} صفحة... استنى شوية.")
            progress_bar = st.progress(0)
            annotations = {}
            
            for i in range(pages_to_process):
                page = doc[i]
                text = page.get_text()
                
                # لو الصفحة فيها نص كفاية
                if len(text.strip()) > 50:
                    prompt = f"""
                    أنت خبير تعليمي. اقرأ النص التالي من صفحة كتاب، وصمم عناصر تفاعلية (أسئلة اختيار من متعدد أو حقول إجابة).
                    النص: {text[:3000]}
                    
                    أرجع النتيجة بصيغة JSON فقط (بدون أي كلام إضافي) بهذا الشكل:
                    {{
                        "elements": [
                            {{"type": "choice", "question": "السؤال هنا؟", "options": ["أ", "ب", "ج"], "correct": 0}},
                            {{"type": "text", "question": "اكتب إجابتك هنا", "answer": "الإجابة المتوقعة"}}
                        ]
                    }}
                    """
                    
                    try:
                        response = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama3-8b-8192",
                            response_format={"type": "json_object"}
                        )
                        result = json.loads(response.choices[0].message.content)
                        annotations[i+1] = result.get("elements", [])
                    except Exception as ai_err:
                        st.warning(f"تخطي صفحة {i+1} بسبب خطأ في الذكاء الاصطناعي.")
                
                progress_bar.progress((i + 1) / pages_to_process)
            
            # توليد الـ HTML
            html_content = f"""
            <!DOCTYPE html>
            <html dir="rtl"><head><meta charset="utf-8"><title>الكتاب التفاعلي</title>
            <style>
                body {{ font-family: system-ui, sans-serif; padding: 20px; background: #f0f2f5; max-width: 800px; margin: auto; }}
                .page {{ background: #fff; padding: 20px; margin-bottom: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,.1); }}
                .q {{ margin-bottom: 15px; padding: 10px; border-right: 4px solid #2563eb; background: #f8fafc; }}
                .q h4 {{ margin: 0 0 10px 0; }}
                label {{ display: block; margin-bottom: 5px; cursor: pointer; }}
                input[type="text"] {{ width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 5px; }}
            </style></head><body>
            <h1>📖 الكتاب التفاعلي المولد تلقائياً</h1>
            <div id="app"></div>
            <script>
                const data = {json.dumps(annotations)};
                const app = document.getElementById('app');
                for (const page in data) {{
                    const pageDiv = document.createElement('div');
                    pageDiv.className = 'page';
                    pageDiv.innerHTML = `<h3>أساسيات من الصفحة ${{page}}</h3>`;
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
                label="⬇️ تحميل ملف الكتاب التفاعلي (HTML)",
                data=html_content,
                file_name="interactive_book.html",
                mime="text/html"
            )
            
            os.remove("temp.pdf")
            
        except Exception as e:
            st.error(f"حدث خطأ: {str(e)}")