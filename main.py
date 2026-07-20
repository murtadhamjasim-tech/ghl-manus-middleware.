
import os
import time
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

app = FastAPI()

# إضافة CORS Middleware لحل مشكلة Cross-Origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # السماح من أي موقع
    allow_credentials=True,
    allow_methods=["*"],  # السماح بجميع الطرق (GET, POST, PUT, DELETE, إلخ)
    allow_headers=["*"],  # السماح بجميع الـ Headers
)

# Configuration from environment variables
MANUS_API_KEY = os.getenv("MANUS_API_KEY")
GHL_WEBHOOK_URL = os.getenv("GHL_WEBHOOK_URL")  # The URL in GHL to send results back
MANUS_API_BASE = "https://api.manus.ai/v2"

class PaymentVerificationRequest(BaseModel):
    image_url: str
    transaction_id: str
    amount: float
    contact_id: str  # To identify the student in GHL

def upload_to_manus(image_url: str):
    # Step 1: Download image from GHL URL
    img_response = requests.get(image_url)
    if img_response.status_code != 200:
        raise Exception("Failed to download image from GoHighLevel")
    
    # Step 2: Upload to Manus
    files = {'file': ('payment_proof.png', img_response.content, 'image/png')}
    headers = {"x-manus-api-key": MANUS_API_KEY}
    response = requests.post(f"{MANUS_API_BASE}/file.upload", headers=headers, files=files)
    
    if response.status_code != 200:
        raise Exception(f"Manus Upload Failed: {response.text}")
    
    return response.json()["data"]["file_id"]

def create_manus_verification_task(file_id: str, transaction_id: str, amount: float):
    headers = {
        "x-manus-api-key": MANUS_API_KEY,
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    Please verify the attached payment proof image.
    Match it against the following details:
    - Transaction ID: {transaction_id}
    - Amount: {amount}
    
    Check if the image clearly shows a successful payment with these exact details.
    """
    
    payload = {
        "message": {
            "content": prompt,
            "file_ids": [file_id]
        },
        "structured_output_schema": {
            "type": "object",
            "properties": {
                "is_matched": {"type": "boolean", "description": "True if the payment details in the image match the provided details."},
                "confidence_score": {"type": "number", "description": "Confidence score from 0 to 1."},
                "reason": {"type": "string", "description": "Reason for the match or mismatch."}
            },
            "required": ["is_matched", "confidence_score", "reason"],
            "additionalProperties": False
        }
    }
    
    response = requests.post(f"{MANUS_API_BASE}/task.create", headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"Manus Task Creation Failed: {response.text}")
    
    return response.json()["data"]["task_id"]

def poll_manus_result(task_id: str):
    headers = {"x-manus-api-key": MANUS_API_KEY}
    
    # Simple polling logic (for production, use webhooks)
    for _ in range(30):  # Poll for up to 5 minutes (10s intervals)
        response = requests.get(f"{MANUS_API_BASE}/task.listMessages?task_id={task_id}&order=desc", headers=headers)
        if response.status_code == 200:
            messages = response.json()["data"]["messages"]
            for msg in messages:
                if msg["type"] == "structured_output_result":
                    return msg["structured_output_result"]
        
        time.sleep(10)
    
    return None

def process_verification(data: PaymentVerificationRequest):
    try:
        # 1. Upload Image
        file_id = upload_to_manus(data.image_url)
        
        # 2. Create Verification Task
        task_id = create_manus_verification_task(file_id, data.transaction_id, data.amount)
        
        # 3. Poll for result
        result = poll_manus_result(task_id)
        
        if result and result["success"]:
            verification_data = result["value"]
            # 4. Send back to GHL
            ghl_payload = {
                "contact_id": data.contact_id,
                "is_verified": verification_data["is_matched"],
                "reason": verification_data["reason"],
                "transaction_id": data.transaction_id
            }
            requests.post(GHL_WEBHOOK_URL, json=ghl_payload)
            
    except Exception as e:
        print(f"Error processing verification: {str(e)}")

@app.post("/verify-payment")
async def verify_payment(
    image_url: str = Form(...),
    transaction_id: str = Form(...),
    amount: float = Form(...),
    contact_id: str = Form(...),
    background_tasks: BackgroundTasks = None
):
    """
    استقبال بيانات الدفع والتحقق منها باستخدام Manus AI
    """
    try:
        print(f"[{datetime.now()}] استقبال طلب تحقق من الدفع")
        print(f"Transaction ID: {transaction_id}")
        print(f"Amount: {amount}")
        print(f"Contact ID: {contact_id}")
        print(f"Image URL: {image_url}")

        # إنشاء كائن الطلب
        request_data = PaymentVerificationRequest(
            image_url=image_url,
            transaction_id=transaction_id,
            amount=amount,
            contact_id=contact_id
        )

        # معالجة التحقق في الخلفية
        if background_tasks:
            background_tasks.add_task(process_verification, request_data)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status": "processing",
                "message": "تم استقبال البيانات وجاري التحقق منها",
                "transaction_id": transaction_id,
                "contact_id": contact_id,
                "timestamp": datetime.now().isoformat()
            }
        )

    except Exception as e:
        print(f"خطأ: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "message": "حدث خطأ أثناء معالجة الطلب",
                "timestamp": datetime.now().isoformat()
            }
        )

@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """معالج OPTIONS للـ CORS preflight requests"""
    return JSONResponse(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "GHL-Manus-Middleware",
        "timestamp": datetime.now().isoformat()
    }
