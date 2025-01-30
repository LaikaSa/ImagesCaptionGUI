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
            
        try:
            self.download_button.setEnabled(False)
            self.status_label.setText("Starting download...")
            
            # Get API configuration from parent window
            api_url = self.parent().api_url.rstrip('/') + '/v1/download'
            headers = {
                'Authorization': f'Bearer {self.parent().api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "repo_id": repo_id,
                "folder_name": None,  # Use default folder name
                "revision": None,     # Use default revision
                "token": None,        # No HF token
                "chunk_limit": None,  # Use default chunk size
                "repo_type": "model"
            }
            
            response = requests.post(api_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                QMessageBox.information(self, "Success", "Model downloaded successfully!")
                self.parent().refresh_models()  # Refresh model list
                self.accept()
            else:
                QMessageBox.critical(self, "Error", f"Download failed: {response.text}")
                self.download_button.setEnabled(True)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Download failed: {str(e)}")
            self.download_button.setEnabled(True)