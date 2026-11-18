"""Train/evaluate UAIT classifier with a fixed test split and save the model."""
from pathlib import Path
import pandas as pd, joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'intents.csv'
df=pd.read_csv(DATA)
train=df[df.split=='train']; test=df[df.split=='test']
model=make_pipeline(TfidfVectorizer(analyzer='char_wb',ngram_range=(2,5)),CalibratedClassifierCV(LinearSVC(),cv=3))
model.fit(train.text.astype(str),train.intent.astype(str))
score=(model.predict(test.text.astype(str))==test.intent.astype(str)).mean()
print(f'Fixed test set: {len(test)} messages; accuracy: {score:.1%}')
joblib.dump(model,ROOT/'intent_classifier.joblib')
print('Saved intent_classifier.joblib')
