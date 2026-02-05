import os
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# SECURITY: Allow your GitHub Pages URL to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Change this to your GitHub URL for production
    allow_methods=["POST"],
    allow_headers=["*"],
)

def get_db_connection():
    try:
        # Configuration for AWS Aurora
        conn = psycopg2.connect(
            dbname="uk_rcc_dev",
            user="postgres",
            password="postgres123",
            host="aurora-postgresql.holcim.net",
            port="5432",
            sslmode='require'
        )
        return conn
    except Exception as e:
        print(f"Error connecting to Aurora: {e}")
        return None

class AuditResult(BaseModel):
    section: str
    q: str
    res: str

class AuditSubmission(BaseModel):
    serial: str
    orderNumber: str
    auditee: str
    participants: str
    status: str
    results: List[AuditResult]

@app.post("/api/v1/audit/submit")
async def submit_to_aurora(payload: AuditSubmission):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    cur = conn.cursor()
    try:
        # 1. Insert Master Record
        cur.execute(
            """INSERT INTO audits_master (serial_number, order_number, auditee_name, participants, status) 
               VALUES (%s, %s, %s, %s, %s) RETURNING audit_id""",
            (payload.serial, payload.orderNumber, payload.auditee, payload.participants, payload.status)
        )
        audit_id = cur.fetchone()[0]

        # 2. Insert all 33 responses
        for item in payload.results:
            cur.execute(
                """INSERT INTO audit_responses (audit_id, section_title, question, result) 
                   VALUES (%s, %s, %s, %s)""",
                (audit_id, item.section, item.q, item.res)
            )

        conn.commit()
        print(f"Audit {payload.serial} saved successfully.")
        return {"status": "success", "audit_id": audit_id}
    
    except Exception as e:
        conn.rollback()
        print(f"SQL Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()