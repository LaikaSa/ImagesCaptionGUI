from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, 
                             QLineEdit, QPushButton, QLabel, QMessageBox)
import requests

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

        def download_task(repo_id, api_url, api_key):
            api_url = api_url.rstrip('/') + '/v1/download'
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
            
            response = requests.post(api_url, headers=headers, json=payload)
            if response.status_code != 200:
                raise Exception(f"Download failed: {response.text}")
            return response.json()

        self.download_button.setEnabled(False)
        self.status_label.setText("Downloading model...")

        # Create and start worker thread
        self.worker = WorkerThread(
            download_task, 
            repo_id, 
            self.parent().api_url, 
            self.parent().api_key
        )
        self.worker.finished.connect(self.on_download_complete)
        self.worker.error.connect(self.on_download_error)
        self.worker.start()

    def on_download_complete(self, result):
        self.download_button.setEnabled(True)
        QMessageBox.information(self, "Success", "Model downloaded successfully!")
        self.parent().refresh_models()
        self.accept()

    def on_download_error(self, error_msg):
        self.download_button.setEnabled(True)
        self.status_label.setText("")
        QMessageBox.critical(self, "Error", str(error_msg))