from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from models import SurveySubmission, StoredSurveyRecord
from storage import append_json_line
from pydantic import BaseModel
from typing import Optional
import hashlib

app = Flask(__name__)
# Allow cross-origin requests so the static HTML can POST from localhost or file://
CORS(app, resources={r"/v1/*": {"origins": "*"}})

@app.route("/ping", methods=["GET"])
def ping():
    """Simple health check endpoint."""
    return jsonify({
        "status": "ok",
        "message": "API is alive",
        "utc_time": datetime.now(timezone.utc).isoformat()
    })

@app.post("/v1/survey")
def submit_survey():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "invalid_json", "detail": "Body must be application/json"}), 400

    try:
        submission = SurveySubmission(**payload)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "detail": ve.errors()}), 422

    record = StoredSurveyRecord(
        **submission.dict(),
        received_at=datetime.now(timezone.utc),
        ip=request.headers.get("X-Forwarded-For", request.remote_addr or "")
        submission_id = generate_submission_id(submission.email)
    )
    append_json_line(record.dict())
    return jsonify({"status": "ok"}), 201

if __name__ == "__main__":
    app.run(port=0, debug=True)

class Submission(BaseModel):
    email: str
    age: int
    submission_id: Optional[str] = None
    user_agent: Optional[str] = None

def hash_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def generate_submission_id(email: str) -> str:
    now = datetime.utcnow().strftime("%Y%m%d%H")
    return hash_sha256(email + now)

def save_submission(submission: Submission):
    record = {
        "email": hash_sha256(submission.email),
        "age": hash_sha256(str(submission.age)),
        "submission_id": submission.submission_id,
        "user_agent": submission.user_agent
    }
    with open("submissions.json", "a") as f:
        f.write(f"{record}\n")

@app.post("/submit")
def submit(submission: Submission):
    if not submission.submission_id:
        submission.submission_id = generate_submission_id(submission.email)
    save_submission(submission)
    return {"message": "Submission saved successfully", "submission_id": submission.submission_id}
