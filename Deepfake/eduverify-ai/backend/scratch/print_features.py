import sys, cv2, numpy as np
sys.path.insert(0, r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend")
from evaluation.train_classifier import extract_features_from_image, FEATURE_NAMES

img = cv2.imread(r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend\evaluation\images\ai_generated\Handwritten Winter Essay.png")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
feat = extract_features_from_image(gray)
for name, val in zip(FEATURE_NAMES, feat):
    print(f"{name:20s}: {val:.4f}")

