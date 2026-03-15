import cv2
import numpy as np
import face_recognition
import json
from app.database import SessionLocal
from app.models import Employee

# In-memory Cache for Face Encodings to save DB calls and improve speed
ENCODINGS_CACHE = {}

def load_encodings_to_cache():
    """Loads all face encodings from database into memory on startup."""
    db = SessionLocal()
    try:
        employees = db.query(Employee).all()
        for emp in employees:
            # Convert JSON string back to numpy array
            encoding_list = json.loads(emp.face_encoding)
            ENCODINGS_CACHE[emp.employee_id] = np.array(encoding_list)
        print(f"Loaded {len(ENCODINGS_CACHE)} face encodings into cache.")
    except Exception as e:
        print(f"Error loading cache: {e}")
    finally:
        db.close()

def add_to_cache(employee_id: str, encoding: np.ndarray):
    ENCODINGS_CACHE[employee_id] = encoding

def process_image_and_get_encoding(image_bytes: bytes) -> np.ndarray:
    """Reads image bytes, resizes for performance, and extracts face encoding."""
    # Convert bytes to numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Invalid image file.")

    # Resize image to 25% for faster face detection (Optimization for Render)
    small_img = cv2.resize(img, (0, 0), fx=0.25, fy=0.25)
    
    # Convert from BGR (OpenCV) to RGB (face_recognition)
    rgb_small_img = cv2.cvtColor(small_img, cv2.COLOR_BGR2RGB)

    # Detect faces using 'hog' model (faster/lighter than 'cnn')
    face_locations = face_recognition.face_locations(rgb_small_img, model="hog")

    if len(face_locations) == 0:
        raise ValueError("No face detected in the image.")
    if len(face_locations) > 1:
        raise ValueError("Multiple faces detected. Please ensure only one face is in the frame.")

    # Get encoding
    face_encodings = face_recognition.face_encodings(rgb_small_img, face_locations)
    return face_encodings[0]

def recognize_face(image_bytes: bytes, threshold: float = 0.5) -> str:
    """Matches uploaded image against cached encodings."""
    if not ENCODINGS_CACHE:
        raise ValueError("No registered employees found in the system.")

    unknown_encoding = process_image_and_get_encoding(image_bytes)
    
    known_employee_ids = list(ENCODINGS_CACHE.keys())
    known_encodings = list(ENCODINGS_CACHE.values())

    # Calculate face distances
    face_distances = face_recognition.face_distance(known_encodings, unknown_encoding)
    best_match_index = np.argmin(face_distances)

    if face_distances[best_match_index] <= threshold:
        return known_employee_ids[best_match_index]
    
    raise ValueError("Face does not match any registered employee.")
