# UAIT Admissions Assistant capstone

A Streamlit chatbot for prospective students and families asking about United African Institute of Technology (UAIT) programmes and admissions. This adapts the supplied UAIt assistant to the capstone's required rules → intent classifier → fallback flow. It uses the included verified facts and knowledge seed; no language model key is needed.

## Live link

Not deployed yet. After you push this repository to your public GitHub account and deploy `streamlit/app.py` on Streamlit Community Cloud, add the live URL here. A repository URL is due 18 November 2026 at 23:59, and the demonstration is 19 November 2026, per the supplied brief.

## Purpose and users

The assistant helps prospective students find general information. It is not an official admissions decision or a replacement for contacting UAIT. The source project contains some items marked for owner confirmation; have UAIT verify those before relying on them publicly.

## Intents

| Intent | Example user need | Route |
|---|---|---|
| greeting / identity / thanks | start a conversation or ask what the bot is | Rules, then classifier |
| fees | tuition, costs, instalments | Rules, then classifier |
| apply | application and enrolment steps | Rules, then classifier |
| programmes | available courses | Rules, then classifier |
| documents | entry requirements and papers | Rules, then classifier |
| contact | admissions contact and location | Rules, then classifier |
| dates | application period and deadline | Rules, then classifier |
| goodbye | end the conversation | Rules, then classifier |
| out of scope / low confidence | unrelated question or uncertain prediction | Fallback |

The classifier threshold is `0.42` in `streamlit/app.py`. Rules run first; only messages not caught by a rule reach the classifier. The included CSV separates training rows and a fixed test set.

## How it works

1. Normalize whitespace and check ordered regular-expression rules.
2. For unmatched wording, use a character n-gram TF-IDF + calibrated linear SVM classifier.
3. Accept a prediction at confidence 0.42 or above; otherwise show the UAIT-specific fallback.
4. For an in-scope admissions question, the existing assistant retrieves its verified facts and knowledge records. Goodbye closes the chat and offers a new conversation.
5. A random visitor code and each turn can be sent to a private Google Sheet through Apps Script. No names or contact details are requested.

Example flow: visitor asks “what can I study?” → classifier identifies `programmes` if no rule matches → verified knowledge assistant responds → visitor asks a follow-up → assistant uses its knowledge retrieval → visitor says “goodbye” → conversation closes.

## Test results

Run `python train_classifier.py` to train and report accuracy on the included unchanged test rows. The initial score is intentionally not claimed here because it has not been measured in this environment. Add real varied test conversations and document one bug plus its fix before submission.

## What users wrote and what changed

Not populated yet: this requires real, consent-notified use through your own private Sheet. After deployment, review the log, label relevant messages, append only anonymised message/intent rows to `intents.csv` with `source=log` and `split=train`, and rerun `python train_classifier.py`. Keep every `split=test` row unchanged and compare both versions on that same set. Record the actual before/after scores and 3–4 anonymised examples here. Never commit the raw log or Sheet URL.

## Limits and next improvement

The classifier is trained on a small starter dataset and may miss local phrasing or Kinyarwanda/Korean messages; add reviewed examples before claiming broad language support. The answer knowledge may be stale or contain unresolved owner-confirmation items. Next: have UAIT verify the facts, collect consented messages, label failure cases, and improve the training set. The optional model/RAG features in the original project are not enabled by this Streamlit capstone.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python train_classifier.py
streamlit run streamlit/app.py
```

For deployment, set the Streamlit main file to `streamlit/app.py`. To log turns, deploy `apps_script.gs` as a Google Apps Script web app and add `LOG_URL = "your private deployment URL"` to Streamlit secrets. Do not put that URL in GitHub. Without the secret, answers still work, but turns are not logged and this capstone requirement is incomplete.

`intents.csv` is training data, not the real user log. `data/facts.json` and `data/knowledge_seed.json` are the assistant's source material. The original assistant architecture and deployment notes are retained in `DEPLOY.md`.
