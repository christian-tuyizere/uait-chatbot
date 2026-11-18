"""UAIT capstone chatbot: rules, intent classifier, then fallback."""
import re, sys
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import joblib, pandas as pd, requests, streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.assistant import Assistant
THRESHOLD=0.42
RULES=[("goodbye",r"^\s*(bye|goodbye|see you|talk later|quit|exit)\b"),("greeting",r"^\s*(hi|hello|hey|muraho|good morning|good afternoon)\b"),("thanks",r"^\s*(thanks?|thank you|thx)\b"),("identity",r"\b(who are you|what are you|your name)\b"),("fees",r"\b(fee|fees|tuition|cost|price|how much|instal+ments?)\b"),("apply",r"\b(apply|application|admission process|enrol|enroll|register)\b"),("programmes",r"\b(programme|program|course|what can i study)\b"),("documents",r"\b(document|transcript|requirement|passport|paperwork)\b"),("contact",r"\b(contact|email|phone|address|located|where is the campus)\b"),("dates",r"\b(deadline|closing date|application dates|when does admission close)\b")]
FALLBACK="I can help with UAIT programmes, admissions, fees, application documents, dates, and contacts. Which would you like to know about?"
@st.cache_resource
def load_model():
 p=ROOT/"intent_classifier.joblib"
 if p.exists(): return joblib.load(p)
 df=pd.read_csv(ROOT/"intents.csv"); train=df[df.split=="train"]
 model=make_pipeline(TfidfVectorizer(analyzer="char_wb",ngram_range=(2,5)),CalibratedClassifierCV(LinearSVC(),cv=3))
 model.fit(train.text.astype(str),train.intent.astype(str)); return model
@st.cache_resource
def get_assistant(): return Assistant()
def route(message,model):
 clean=re.sub(r"\s+"," ",message.strip())
 for intent,pattern in RULES:
  if re.search(pattern,clean,re.I): return intent,1.0,"rules"
 scores=model.predict_proba([clean])[0]; i=scores.argmax(); intent=str(model.classes_[i]); confidence=float(scores[i])
 return (intent,confidence,"classifier") if confidence>=THRESHOLD and intent!="out_of_scope" else ("out_of_scope",confidence,"fallback")
def log_row(row):
 try: url=st.secrets.get("LOG_URL","")
 except Exception: url=""
 if not url:return False
 try:
  r=requests.post(url,json=row,timeout=8);return r.ok and r.text.strip()=="ok"
 except requests.RequestException:return False
st.set_page_config(page_title="UAIT Admissions Assistant",page_icon="🎓")
st.title("UAIT Admissions Assistant")
st.caption("Student capstone chatbot for general UAIT information. It cannot make official admissions decisions.")
st.info("Messages are recorded to improve this chatbot. Please do not enter names, phone numbers, or identity numbers.")
ss=st.session_state;ss.setdefault("visitor",uuid4().hex[:12]);ss.setdefault("messages",[]);ss.setdefault("closed",False)
model=load_model(); assistant=get_assistant()
for m in ss.messages:
 with st.chat_message(m["role"]):
  st.markdown(m["text"])
  if m.get("answered_by"):st.caption("answered by: "+m["answered_by"])
if ss.closed:
 if st.button("Start a new conversation"):ss.messages=[];ss.closed=False;st.rerun()
else:
 prompt=st.chat_input("Ask about studying at UAIT")
 if prompt:
  ss.messages.append({"role":"user","text":prompt});intent,confidence,by=route(prompt,model)
  if intent=="goodbye":answer="Thank you for visiting. Goodbye!";ss.closed=True
  elif by=="fallback":answer=FALLBACK
  elif intent in {"greeting","thanks","identity"}:answer={"greeting":"Hello! I can answer questions about UAIT programmes and admissions.","thanks":"You’re welcome. What else would you like to know?","identity":"I’m a student-built UAIT information assistant, not an admissions officer."}[intent]
  else:
   try:answer=assistant.respond(prompt,history=[],ui_lang="en").get("answer",FALLBACK)
   except Exception:answer=FALLBACK;by="fallback"
  ss.messages.append({"role":"assistant","text":answer,"answered_by":by})
  row={"time":datetime.now(timezone.utc).isoformat(),"user":ss.visitor,"turn":sum(m["role"]=="user" for m in ss.messages),"message":prompt,"intent":intent,"confidence":round(confidence,3),"answered_by":by,"reply":answer,"feedback":""}
  if not log_row(row):st.warning("This turn was not saved. Set LOG_URL in Streamlit secrets to enable the private learning log.")
  st.rerun()
