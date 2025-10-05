import firebase_admin
from firebase_admin import credentials, firestore

# cred = credentials.Certificate() ! Put the paath to the service account key here
firebase_admin.initialize_app(cred)

print("Project ID:", cred.project_id)
print("Client email (service account):", cred.service_account_email)

db = firestore.client()

doc_id = "example_1"
db.collection("test_docs").document(doc_id).set({
    "name": "Test document",
    "score": 42,
    "created_at": firestore.SERVER_TIMESTAMP,
})