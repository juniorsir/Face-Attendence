import cv2
import numpy as np
import face_recognition
import json
from app.database import SessionLocal
from app.models import FaceRegistration
from app.logger import log_debug  # <-- Import the logger

ENCODINGS_CACHE = {}

def load_encodings_to_cache():
    db = SessionLocal()
    try:
        log_debug("Face_Utils", "Starting to load face encodings into cache...")
        registrations = db.query(FaceRegistration).all()
        for reg in registrations:
            if not reg.face_encoding:
                continue
            try:
                encoding_list = json.loads(reg.face_encoding)
                ENCODINGS_CACHE[reg.employee_id] = np.array(encoding_list)
            except json.JSONDecodeError:
                continue

        print(f"✅ Loaded {len(ENCODINGS_CACHE)} valid face registrations into cache.")
        log_debug("Face_Utils", f"Cache loaded successfully with {len(ENCODINGS_CACHE)} faces.")
    except Exception as e:
        print(f"❌ Error loading cache: {e}")
    finally:
        db.close()

def add_to_cache(employee_id: str, encoding: np.ndarray):
    ENCODINGS_CACHE[employee_id] = encoding
    log_debug("Face_Utils", f"Added new encoding to cache for {employee_id}")

def process_image_and_get_encoding(image_bytes: bytes) -> np.ndarray:
    log_debug("Face_Utils", "Decoding image bytes...")
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Invalid image file.")

    log_debug("Face_Utils", "Resizing image for faster processing...")
    small_img = cv2.resize(img, (0, 0), fx=0.25, fy=0.25)
    rgb_small_img = cv2.cvtColor(small_img, cv2.COLOR_BGR2RGB)

    log_debug("Face_Utils", "Detecting faces using HOG model...")
    face_locations = face_recognition.face_locations(rgb_small_img, model="hog")
    log_debug("Face_Utils", f"Found {len(face_locations)} face(s) in image.")

    if len(face_locations) == 0:
        raise ValueError("No face detected in the image.")
    if len(face_locations) > 1:
        raise ValueError("Multiple faces detected. Please ensure only one face is in the frame.")

    face_encodings = face_recognition.face_encodings(rgb_small_img, face_locations)
    return face_encodings[0]

def recognize_face(image_bytes: bytes, threshold: float = 0.5) -> str:
    if not ENCODINGS_CACHE:
        raise ValueError("No registered faces found in the system cache.")

    log_debug("Face_Utils", "Extracting encoding from uploaded image...")
    unknown_encoding = process_image_and_get_encoding(image_bytes)
    
    known_ids = list(ENCODINGS_CACHE.keys())
    known_encodings = list(ENCODINGS_CACHE.values())

    log_debug("Face_Utils", f"Comparing unknown face against {len(known_encodings)} known faces...")
    face_distances = face_recognition.face_distance(known_encodings, unknown_encoding)
    best_match_index = np.argmin(face_distances)
    best_distance = face_distances[best_match_index]

    log_debug("Face_Utils", f"Best match distance: {best_distance:.4f} (Threshold: {threshold})")

    if best_distance <= threshold:
        matched_id = known_ids[best_match_index]
        log_debug("Face_Utils", f"✅ Match successful! Identified as {matched_id}")
        return matched_id
    
    log_debug("Face_Utils", "❌ Face did not match any registered employee.")
    raise ValueError("Face does not match any registered employee.")

def check_duplicate_face(new_encoding: np.ndarray, threshold: float = 0.5) -> str:
    if not ENCODINGS_CACHE:
        return None
        
    known_encodings = list(ENCODINGS_CACHE.values())
    known_ids = list(ENCODINGS_CACHE.keys())

    log_debug("Face_Utils", "Checking for duplicate physical faces...")
    face_distances = face_recognition.face_distance(known_encodings, new_encoding)
    best_match_index = np.argmin(face_distances)

    if face_distances[best_match_index] <= threshold:
        matched_id = known_ids[best_match_index]
        log_debug("Face_Utils", f"⚠️ Duplicate found! Face belongs to {matched_id}")
        return matched_id
    
    return None
