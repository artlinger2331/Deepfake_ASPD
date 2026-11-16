import sys
sys.path.insert(0, r"c:\Users\Pritam Mondal\Desktop\Hacktoberfest\Deepfake\eduverify-ai\backend")
from evaluation.train_classifier import load_dataset
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, roc_auc_score, precision_score, recall_score
import numpy as np

X, y, meta = load_dataset()
winter_idx = [i for i, m in enumerate(meta) if m["image_id"] == "IMG_040"][0]

for d in [3, 4, 5, 6, None]:
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof = np.zeros(len(y))
    for tr, val in skf.split(X, y):
        clf = RandomForestClassifier(n_estimators=100, max_depth=d, class_weight="balanced", random_state=42)
        clf.fit(X[tr], y[tr])
        oof[val] = clf.predict_proba(X[val])[:, 1]
    acc = accuracy_score(y, (oof >= 0.50).astype(int))
    auc = roc_auc_score(y, oof)
    clf_full = RandomForestClassifier(n_estimators=100, max_depth=d, class_weight="balanced", random_state=42).fit(X, y)
    full_winter_p = clf_full.predict_proba(X[winter_idx:winter_idx+1])[0][1]
    print(f"RF depth={str(d):4s}: OOF Acc={acc*100:.1f}%, OOF AUC={auc*100:.1f}%, Winter P={full_winter_p:.4f}")

# Also test GradientBoosting
for lr in [0.05, 0.1]:
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof = np.zeros(len(y))
    for tr, val in skf.split(X, y):
        gb = GradientBoostingClassifier(n_estimators=80, learning_rate=lr, max_depth=3, random_state=42)
        gb.fit(X[tr], y[tr])
        oof[val] = gb.predict_proba(X[val])[:, 1]
    acc = accuracy_score(y, (oof >= 0.50).astype(int))
    auc = roc_auc_score(y, oof)
    gb_full = GradientBoostingClassifier(n_estimators=80, learning_rate=lr, max_depth=3, random_state=42).fit(X, y)
    full_winter_p = gb_full.predict_proba(X[winter_idx:winter_idx+1])[0][1]
    print(f"GB lr={lr:<4f}: OOF Acc={acc*100:.1f}%, OOF AUC={auc*100:.1f}%, Winter P={full_winter_p:.4f}")
