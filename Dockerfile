# Use the official Miniconda image (Pre-loaded with Python and Conda)
FROM continuumio/miniconda3:latest

# Set working directory
WORKDIR /app

# 1. Install heavy Machine Learning libraries via Conda (Pre-compiled, ZERO RAM compilation!)
RUN conda install -y -c conda-forge \
    dlib \
    face_recognition \
    numpy \
    opencv \
    && conda clean -afy

# 2. Copy your project files into the container
COPY . /app

# 3. Install lightweight web dependencies via pip
RUN pip install --no-cache-dir -r requirements.txt

# Start the FastAPI application
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
