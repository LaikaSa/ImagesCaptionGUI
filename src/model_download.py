from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, 
                             QLineEdit, QPushButton, QLabel, QMessageBox)
import requests
from src.worker_thread import WorkerThread

class ModelDownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Model")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Create form layout for inputs
        form_layout = QFormLayout()
        
        # Repo ID input
        self.repo_input = QLineEdit()
        self.repo_input.setPlaceholderText("e.g., Minthy/ToriiGate-v0.4-7B")
        form_layout.addRow("Repository ID:", self.repo_input)
        
        layout.addLayout(form_layout)
        
        # Download button
        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.start_download)
        layout.addWidget(self.download_button)
        
        # Status label
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def start_download(self):
        repo_id = self.repo_input.text().strip()
        if not repo_id:
            QMessageBox.warning(self, "Error", "Please enter a repository ID")
            return

        print(f"Starting download request for repo: {repo_id}")

        def download_task(api_url=None, api_key=None, repo_id=None):
            """Send download request to server"""
            # Use the correct endpoint
            request_url = f"{api_url.rstrip('/')}/v1/download"  # Changed from /v1/model/download
            print(f"Sending request to: {request_url}")
            
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "repo_id": repo_id,
                "folder_name": None,
                "revision": None,
                "token": None,
                "chunk_limit": None,
                "repo_type": "model"
            }
            
            response = requests.post(request_url, headers=headers, json=payload)
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text}")
            
            if response.status_code != 200:
                raise Exception(f"Download request failed: {response.text}")
                
            return response.json()

        self.download_button.setEnabled(False)
        self.status_label.setText("Sending download request...")

        # Create worker thread with kwargs
        self.worker = WorkerThread(
            task_func=download_task,
            api_url=self.parent().api_url,
            api_key=self.parent().api_key,
            repo_id=repo_id
        )
        self.worker.finished.connect(self.on_download_complete)
        self.worker.error.connect(self.on_download_error)
        self.worker.start()

    def on_download_complete(self, result):
        self.download_button.setEnabled(True)
        QMessageBox.information(self, "Success", "Download request sent successfully! The server will handle the download.")
        self.parent().refresh_models()
        self.accept()

    def on_download_error(self, error_msg):
        self.download_button.setEnabled(True)
        self.status_label.setText("")
        QMessageBox.critical(self, "Error", str(error_msg))