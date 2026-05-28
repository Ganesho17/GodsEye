import cv2
import numpy as np
from detection.yolo_detector import YoloDetector
import time

yolo = YoloDetector(model_path="models/yolov8s.pt")
while not yolo.model_loaded:
    time.sleep(0.1)

frame = np.zeros((480, 640, 3), dtype=np.uint8)
detections = yolo.process_frame(frame)
print("Detections with yolov8s:", detections)

yolo_n = YoloDetector(model_path="models/yolov8n.pt")
while not yolo_n.model_loaded:
    time.sleep(0.1)

detections_n = yolo_n.process_frame(frame)
print("Detections with yolov8n:", detections_n)
