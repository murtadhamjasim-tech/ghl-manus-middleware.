# برنامج وسيط GoHighLevel-Manus AI للتحقق من الدفع

يهدف هذا المشروع إلى توفير برنامج وسيط (Middleware) يعمل على Render لربط منصة GoHighLevel مع Manus AI API. وظيفته الأساسية هي استلام بيانات إثبات الدفع (صورة، رقم العملية، المبلغ) من GoHighLevel، ثم استخدام Manus AI للتحقق من صحة هذه البيانات، وإعادة إرسال نتيجة التحقق إلى GoHighLevel.

## 1. معمارية النظام
يتكون النظام من:
*   **منصة GoHighLevel**: لجمع بيانات الدفع.
*   **البرنامج الوسيط (FastAPI)**: مستضاف على Render لمعالجة البيانات.
*   **Manus AI API**: لتحليل الصور والتحقق من البيانات.

## 2. المتطلبات الأساسية
*   حساب GoHighLevel.
*   حساب Manus AI ومفتاح API.
*   حساب Render.

## 3. إعداد المتغيرات البيئية في Render
يجب إضافة هذه القيم في قسم (Environment Variables):
*   `MANUS_API_KEY`: مفتاح الـ API الخاص بمانوس.
*   `GHL_WEBHOOK_URL`: رابط الاستقبال في GoHighLevel.

## 4. كيفية الربط مع GoHighLevel
1. أنشئ Workflow في GHL.
2. أضف خطوة Webhook (POST).
3. استخدم الرابط: `https://your-app.onrender.com/verify-payment`.
4. أرسل البيانات بتنسيق JSON:
   {
     "image_url": "{{رابط_الصورة}}",
     "transaction_id": "{{رقم_العملية}}",
     "amount": {{المبلغ}},
     "contact_id": "{{معرف_الجهة}}"
   }
