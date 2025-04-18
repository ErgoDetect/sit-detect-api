
FROM python:3.10-slim

# กำหนด working directory ใน container
WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

# คัดลอกไฟล์ที่จำเป็นเข้าไป
COPY requirements.txt .

# ติดตั้ง dependencies
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกโปรเจกต์ทั้งหมด
COPY . .

COPY .env .


# เรียกใช้งาน FastAPI ผ่าน uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
