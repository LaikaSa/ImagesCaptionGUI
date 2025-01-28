import os
import json
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QPushButton,
                              QLabel, QFileDialog, QTextEdit, QMessageBox,
                              QDialog, QLineEdit, QFormLayout)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap  # Add this import
import requests
import base64

class APIConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Configuration")
        self.setModal(True)
        
        layout = QFormLayout(self)
        
        self.api_url = QLineEdit(self)
        self.api_key = QLineEdit(self)
        
        # Set default API URL
        self.api_url.setText("http://127.0.0.1:5000")
        
        # Load saved configuration if exists
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.api_url.setText(config.get('api_url', 'http://127.0.0.1:5000'))
                self.api_key.setText(config.get('api_key', ''))
        
        layout.addRow("API URL:", self.api_url)
        layout.addRow("API Key:", self.api_key)
        
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_config)
        layout.addRow(save_button)
    
    def save_config(self):
        config = {
            'api_url': self.api_url.text(),
            'api_key': self.api_key.text()
        }
        with open('config.json', 'w') as f:
            json.dump(config, f)
        self.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Caption Generator")
        self.setMinimumSize(800, 600)
        
        # Load API configuration
        self.load_config()
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add status indicator
        self.status_label = QLabel("Checking backend status...")
        self.status_label.setStyleSheet("color: orange")
        layout.addWidget(self.status_label)
        
        # Create UI elements
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(300)
        self.image_label.setStyleSheet("border: 2px dashed gray;")
        
        self.upload_button = QPushButton("Upload Image")
        self.generate_button = QPushButton("Generate Caption")
        self.config_button = QPushButton("Configure API")
        self.generate_button.setEnabled(False)
        
        self.caption_text = QTextEdit()
        self.caption_text.setReadOnly(True)
        self.caption_text.setPlaceholderText("Generated caption will appear here...")
        
        # Add widgets to layout
        layout.addWidget(self.image_label)
        layout.addWidget(self.upload_button)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.config_button)
        layout.addWidget(self.caption_text)
        
        # Connect signals
        self.upload_button.clicked.connect(self.upload_image)
        self.generate_button.clicked.connect(self.generate_caption)
        self.config_button.clicked.connect(self.show_config_dialog)
        
        self.current_image_path = None
        
        # Create a session for quiet requests
        self.session = requests.Session()
        
        # Start backend status check timer
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_backend_status)
        self.check_timer.start(5000)  # Check every 5 seconds
        self.check_backend_status()  # Initial check

    def load_config(self):
        self.api_url = 'http://127.0.0.1:5000'
        self.api_key = ''
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.api_url = config.get('api_url', 'http://127.0.0.1:5000')
                self.api_key = config.get('api_key', '')

    def show_config_dialog(self):
        dialog = APIConfigDialog(self)
        if dialog.exec_():
            self.load_config()

    def check_backend_status(self):
        try:
            # Use session and stream=True to minimize logging
            response = self.session.get(
                f"{self.api_url}/health", 
                stream=True,
                headers={'Connection': 'close'}
            )
            response.close()  # Close the connection immediately
            
            if response.status_code == 200:
                self.status_label.setText("Backend Status: Connected")
                self.status_label.setStyleSheet("color: green")
                self.generate_button.setEnabled(True if self.current_image_path else False)
            else:
                raise Exception("Backend not responding properly")
        except:
            self.status_label.setText("Backend Status: Not Connected")
            self.status_label.setStyleSheet("color: red")
            self.generate_button.setEnabled(False)

    def upload_image(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        
        if file_name:
            self.current_image_path = file_name
            pixmap = QPixmap(file_name)
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.generate_button.setEnabled(True)

    def generate_caption(self):
        if not self.current_image_path:
            return
        
        if not self.api_url or not self.api_key:
            QMessageBox.warning(self, "Configuration Missing", 
                              "Please configure the API URL and Key first.")
            self.show_config_dialog()
            return
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'accept': 'application/json',
                'Content-Type': 'application/json'
            }

            # Read image as base64
            with open(self.current_image_path, 'rb') as img_file:
                image_base64 = base64.b64encode(img_file.read()).decode('utf-8')

            # Prepare the chat completion request
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": "Please describe this image."
                            }
                        ]
                    }
                ]
            }

            api_url = self.api_url
            if not api_url.endswith('/v1/chat/completions'):
                api_url = api_url.rstrip('/') + '/v1/chat/completions'

            self.caption_text.setText("Generating caption...")
            
            print(f"Sending request to: {api_url}")
            
            response = requests.post(
                api_url,
                headers=headers,
                json=payload
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {response.headers}")
            print(f"Response Body: {response.text}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    if 'choices' in result and len(result['choices']) > 0:
                        caption = result['choices'][0]['message']['content']
                        self.caption_text.setText(caption)
                    else:
                        self.caption_text.setText("No caption generated")
                except ValueError:
                    self.caption_text.setText(f"Error: Could not parse JSON response\n{response.text}")
            else:
                self.caption_text.setText(f"Error: {response.status_code}\n{response.text}")
                    
        except Exception as e:
            self.caption_text.setText(f"Error: {str(e)}")
            print(f"Exception details: {str(e)}")