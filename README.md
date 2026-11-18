# UAIT Admissions Assistant Capstone

A Streamlit chatbot for prospective students and families asking about United African Institute of Technology (UAIT) programmes and admissions. This capstone adapts the supplied UAit assistant to use rules, an intent classifier, and a fallback.

## Live link

[Open the UAIT Admissions Assistant](https://uait-chatbot-yjbwwqz7mht2qvhswdhhba.streamlit.app/)

## Purpose and users

The chatbot helps prospective students and families find general information about UAIT. It is a student project, not an official admissions decision or a replacement for contacting UAIT. Some source information still needs confirmation from UAIT.

## Intents

| Intent | Example user need |
|---|---|
| Greeting, identity, thanks | Start a conversation or ask what the chatbot is |
| Fees | Ask about tuition, costs, or instalments |
| Apply | Ask how to apply or enrol |
| Programmes | Ask which courses are available |
| Documents | Ask about requirements or application papers |
| Contact | Ask for admissions contact details or location |
| Dates | Ask about application dates or deadlines |
| Goodbye | End the conversation |
| Out of scope | Ask something unrelated to UAIT |

## How it works

The chatbot checks ordered rules first. If no rule matches, it uses a character n-gram TF-IDF and calibrated linear SVM classifier. The confidence threshold is `0.42`. Predictions below the threshold reach the fallback. In-scope admissions questions are answered using the supplied verified facts and knowledge records. Saying goodbye closes the conversation.

The app displays which part answered each message, such as `rules`, `classifier`, or `fallback`.

Example dialogue flow: a visitor asks about available programmes; the chatbot identifies the `programmes` intent and answers from its knowledge records; the visitor asks a follow-up; the visitor says goodbye and the chatbot closes the conversation.

## Test results

A manual check on the deployed app showed that `hi` received a greeting from the rules. The message `how can I join` reached the fallback, even though it is an in-scope admissions question. This is a known issue that needs to be corrected and retested.

A full varied-message test table and measured classifier accuracy have not been completed yet. Run `python train_classifier.py` to measure accuracy on the fixed test rows in `intents.csv`. Record the actual result here; do not estimate or invent a score.

## What users wrote and what changed

Real user feedback has not been collected and used for retraining yet. Google Sheet logging must first be configured with the private `LOG_URL` secret. Once real messages are collected, label relevant messages and add anonymised examples to `intents.csv` with `source=log` and `split=train`. Keep the existing test rows unchanged, retrain, and report before-and-after accuracy on that same test set here.

Do not commit the raw log, the Sheet URL, or personal information.

## Limits and next improvement

The classifier uses a small starter dataset and may not understand local phrasing or other languages reliably. Some information in the source knowledge still needs UAIT confirmation. The next improvement is to correct the in-scope `how can I join` routing issue, test varied messages, configure private logging, and retrain using reviewed user messages.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python train_classifier.py
streamlit run streamlit/app.py
```

## Logging setup

To save turns to a private Google Sheet, deploy `apps_script.gs` as a Google Apps Script web app and add its URL as `LOG_URL` in Streamlit app secrets. Do not commit that URL to GitHub. Until logging is configured, turns are not saved and the real-user improvement requirement is incomplete.

`intents.csv` contains classifier training and test examples, not the real user log. The chatbot’s source material is in `data/facts.json` and `data/knowledge_seed.json`.
