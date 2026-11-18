# Deployment notes for the UAIt capstone Streamlit app

1. Push the contents of this project to a public GitHub repository.
2. In Streamlit Community Cloud, select that repository and set the main file to `streamlit/app.py`.
3. Deploy. The app trains the starter classifier from `intents.csv` on first start. For repeatable deployment, run `python train_classifier.py` locally and commit `intent_classifier.joblib` only when the environment version matches `requirements.txt`; otherwise let the app train at startup.
4. For private Google Sheet logging, install `apps_script.gs` as a web app and add `LOG_URL = "..."` to Streamlit's app secrets. Keep the URL private. Without it, chatbot answers work but no log is recorded.
5. Open the live app in a signed-out browser or phone and complete the demonstration script in the capstone README.

The original FastAPI/Docker deployment notes do not apply to this Streamlit capstone entry point.
