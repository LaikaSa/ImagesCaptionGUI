import os
import json
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QFileDialog, QTextEdit, QMessageBox, QComboBox,
                              QDialog, QLineEdit, QFormLayout, QProgressBar, QMenuBar,
                              QMenu, QDoubleSpinBox, QSpinBox)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QPixmap
import requests
import base64
import asyncio
from PIL import Image
import io

class BatchProcessThread(QThread):
    progress = Signal(int, int)  # current, total
    finished = Signal(dict)  # results dictionary
    error = Signal(str)  # error message

    def __init__(self, api_url, api_key, image_files, user_prompt, sampling_config):
        super().__init__()
        self.api_url = api_url
        self.api_key = api_key
        self.image_files = image_files
        self.user_prompt = user_prompt
        self.sampling_config = sampling_config
        self.results = {}

    def run(self):
        try:
            for i, image_path in enumerate(self.image_files, 1):
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'accept': 'application/json',
                    'Content-Type': 'application/json'
                }

                with open(image_path, 'rb') as img_file:
                    image_base64 = base64.b64encode(img_file.read()).decode('utf-8')

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
                                    "text": self.user_prompt
                                }
                            ]
                        }
                    ],
                    **self.sampling_config  # Add sampling parameters to payload
                }

                # Send request
                api_url = self.api_url
                if not api_url.endswith('/v1/chat/completions'):
                    api_url = api_url.rstrip('/') + '/v1/chat/completions'

                response = requests.post(
                    api_url,
                    headers=headers,
                    json=payload
                )

                if response.status_code == 200:
                    result = response.json()
                    if 'choices' in result and len(result['choices']) > 0:
                        caption = result['choices'][0]['message']['content']
                        self.results[image_path] = caption

                        # Save caption to file
                        txt_path = os.path.splitext(image_path)[0] + '.txt'
                        with open(txt_path, 'w', encoding='utf-8') as f:
                            f.write(caption)

                self.progress.emit(i, len(self.image_files))

            self.finished.emit(self.results)
        except Exception as e:
            self.error.emit(str(e))

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

class SamplingConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sampling Configuration")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QFormLayout(self)
        
        # Create spin boxes for each parameter
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.1)
        self.temperature.setDecimals(2)
        
        self.top_p = QDoubleSpinBox()
        self.top_p.setRange(0.0, 1.0)
        self.top_p.setSingleStep(0.1)
        self.top_p.setDecimals(2)
        
        self.top_k = QSpinBox()
        self.top_k.setRange(0, 100)
        
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(1, 2000)
        self.max_tokens.setValue(200)
        
        # Add tooltips
        self.temperature.setToolTip("Controls randomness. Higher values make output more random, lower values make it more deterministic.")
        self.top_p.setToolTip("Controls diversity. Lower values make output more focused.")
        self.top_k.setToolTip("Limits the number of tokens to sample from. 0 means no limit.")
        self.max_tokens.setToolTip("Maximum number of tokens to generate.")
        
        # Add widgets to layout
        layout.addRow("Temperature:", self.temperature)
        layout.addRow("Top P:", self.top_p)
        layout.addRow("Top K:", self.top_k)
        layout.addRow("Max Tokens:", self.max_tokens)
        
        # Add save button
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_config)
        layout.addRow(save_button)
        
        # Load existing config if it exists
        self.load_config()
        
    def load_config(self):
        if os.path.exists('sampling_config.json'):
            with open('sampling_config.json', 'r') as f:
                config = json.load(f)
                self.temperature.setValue(config.get('temperature', 1.0))
                self.top_p.setValue(config.get('top_p', 1.0))
                self.top_k.setValue(config.get('top_k', 0))
                self.max_tokens.setValue(config.get('max_tokens', 200))
    
    def save_config(self):
        config = {
            'temperature': self.temperature.value(),
            'top_p': self.top_p.value(),
            'top_k': self.top_k.value(),
            'max_tokens': self.max_tokens.value()
        }
        with open('sampling_config.json', 'w') as f:
            json.dump(config, f)
        self.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize API configuration
        self.api_url = 'http://127.0.0.1:5000'
        self.api_key = ''
        
        # Load API configuration
        self.load_config()

        self.setWindowTitle("Image Caption Generator")
        self.setMinimumSize(800, 600)

        # Initialize sampling config
        self.sampling_config = {
            'temperature': 1.0,
            'top_p': 1.0,
            'top_k': 0,
            'max_tokens': 200
        }
        self.load_sampling_config()
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Define caption styles
        self.caption_styles = {
            "JSON Format": "Describe the picture in structured json-like format.",
            "Detailed": "Give a long and detailed description of the picture.",
            "Brief": "Describe the picture briefly."
        }
        
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
        
        # Create style selection combo box
        style_layout = QHBoxLayout()
        style_label = QLabel("Caption Style:")
        self.style_combo = QComboBox()
        self.style_combo.addItems(self.caption_styles.keys())
        style_layout.addWidget(style_label)
        style_layout.addWidget(self.style_combo)
        style_layout.addStretch()
        
        self.upload_button = QPushButton("Upload Image")
        self.folder_button = QPushButton("Select Folder")
        self.generate_button = QPushButton("Generate Caption")
        self.config_button = QPushButton("Configure API")
        self.generate_button.setEnabled(False)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        
        self.caption_text = QTextEdit()
        self.caption_text.setReadOnly(True)
        self.caption_text.setPlaceholderText("Generated caption will appear here...")
        
        # Add widgets to layout
        layout.addWidget(self.image_label)
        layout.addLayout(style_layout)
        layout.addWidget(self.upload_button)
        layout.addWidget(self.folder_button)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.config_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.caption_text)
        
        # Connect signals
        self.upload_button.clicked.connect(self.upload_image)
        self.folder_button.clicked.connect(self.select_folder)
        self.generate_button.clicked.connect(self.generate_caption)
        self.config_button.clicked.connect(self.show_config_dialog)
        
        self.current_image_path = None
        self.selected_files = []  # Store selected image files
        self.is_batch_mode = False  # Flag for batch processing
        
        # Start backend status check timer
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_backend_status)
        self.check_timer.start(5000)
        self.check_backend_status()


    def process_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder with Images",
            "",
            QFileDialog.ShowDirsOnly
        )
        
        if not folder_path:
            return

        # Get all image files in the folder
        image_files = []
        for file in os.listdir(folder_path):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                image_files.append(os.path.join(folder_path, file))

        if not image_files:
            QMessageBox.warning(self, "No Images", "No supported image files found in the selected folder.")
            return

        # Create and start the batch processing thread
        self.batch_thread = BatchProcessThread(self.api_url, self.api_key, image_files)
        self.batch_thread.progress.connect(self.update_progress)
        self.batch_thread.finished.connect(self.batch_processing_finished)
        self.batch_thread.error.connect(self.batch_processing_error)

        # Disable buttons and show progress bar
        self.upload_button.setEnabled(False)
        self.batch_button.setEnabled(False)
        self.generate_button.setEnabled(False)
        self.progress_bar.setMaximum(len(image_files))
        self.progress_bar.setValue(0)
        self.progress_bar.show()

        self.batch_thread.start()

    def update_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.caption_text.setText(f"Processing image {current} of {total}...")

    def batch_processing_finished(self, results):
        # Re-enable buttons and hide progress bar
        self.upload_button.setEnabled(True)
        self.batch_button.setEnabled(True)
        self.generate_button.setEnabled(self.current_image_path is not None)
        self.progress_bar.hide()

        # Show summary
        summary = f"Processed {len(results)} images.\n\nResults have been saved as .txt files next to the images."
        self.caption_text.setText(summary)

    def batch_processing_error(self, error_message):
        # Re-enable buttons and hide progress bar
        self.upload_button.setEnabled(True)
        self.batch_button.setEnabled(True)
        self.generate_button.setEnabled(self.current_image_path is not None)
        self.progress_bar.hide()

        QMessageBox.critical(self, "Error", f"An error occurred during batch processing:\n{error_message}")

    def load_config(self):
        """Load API configuration from config.json"""
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.api_url = config.get('api_url', 'http://127.0.0.1:5000')
                self.api_key = config.get('api_key', '')

    def show_config_dialog(self):
        """Show the API configuration dialog"""
        dialog = APIConfigDialog(self)
        if dialog.exec_():
            self.load_config()

    def check_backend_status(self):
        try:
            api_url = self.api_url
            if not api_url.endswith('/v1/chat/completions'):
                api_url = api_url.rstrip('/') + '/v1/chat/completions'
                
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'accept': 'application/json'
            }
            
            # Simple test request
            response = requests.get(api_url, headers=headers)
            
            if response.status_code in [200, 404, 405]:  # 404/405 means endpoint exists but wrong method
                self.status_label.setText("Backend Status: Connected")
                self.status_label.setStyleSheet("color: green")
                self.generate_button.setEnabled(True if self.current_image_path else False)
            else:
                raise Exception("Backend not responding properly")
        except Exception as e:
            print(f"Backend connection error: {str(e)}")  # Debug print
            self.status_label.setText("Backend Status: Not Connected")
            self.status_label.setStyleSheet("color: red")
            self.generate_button.setEnabled(False)

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder with Images",
            "",
            QFileDialog.ShowDirsOnly
        )
        
        if not folder_path:
            return

        # Get all image files in the folder
        self.selected_files = []
        for file in os.listdir(folder_path):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                self.selected_files.append(os.path.join(folder_path, file))

        if not self.selected_files:
            QMessageBox.warning(self, "No Images", "No supported image files found in the selected folder.")
            return

        self.is_batch_mode = True
        self.generate_button.setEnabled(True)
        self.caption_text.setText(f"Found {len(self.selected_files)} images. Click 'Generate Caption' to process them.")

        # Show first image as preview
        if self.selected_files:
            self.show_preview(self.selected_files[0])

    def show_preview(self, image_path):
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

    def upload_image(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        
        if file_name:
            self.current_image_path = file_name
            self.is_batch_mode = False
            self.selected_files = []
            self.show_preview(file_name)
            self.generate_button.setEnabled(True)
            self.caption_text.clear()

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # Create Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        # Add Sampling action
        sampling_action = settings_menu.addAction("Sampling")
        sampling_action.triggered.connect(self.show_sampling_dialog)

    def show_sampling_dialog(self):
        dialog = SamplingConfigDialog(self)
        if dialog.exec_():
            self.load_sampling_config()

    def load_sampling_config(self):
        """Load sampling configuration from sampling_config.json"""
        if os.path.exists('sampling_config.json'):
            with open('sampling_config.json', 'r') as f:
                self.sampling_config = json.load(f)
                
    def generate_caption(self):
        if not self.api_url or not self.api_key:
            QMessageBox.warning(self, "Configuration Missing", 
                            "Please configure the API URL and Key first.")
            self.show_config_dialog()
            return

        # Get selected caption style
        selected_style = self.style_combo.currentText()
        user_prompt = self.caption_styles[selected_style]

        if self.is_batch_mode and self.selected_files:
            # Start batch processing
            self.batch_thread = BatchProcessThread(
                self.api_url, 
                self.api_key, 
                self.selected_files, 
                user_prompt,
                self.sampling_config  # Pass sampling config to thread
            )
            self.batch_thread.progress.connect(self.update_progress)
            self.batch_thread.finished.connect(self.batch_processing_finished)
            self.batch_thread.error.connect(self.batch_processing_error)

            # Update UI
            self.upload_button.setEnabled(False)
            self.folder_button.setEnabled(False)
            self.generate_button.setEnabled(False)
            self.progress_bar.setMaximum(len(self.selected_files))
            self.progress_bar.setValue(0)
            self.progress_bar.show()

            self.batch_thread.start()
        else:
            # Single image processing
            try:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'accept': 'application/json',
                    'Content-Type': 'application/json'
                }

                # Read and encode image
                with open(self.current_image_path, 'rb') as img_file:
                    image_base64 = base64.b64encode(img_file.read()).decode('utf-8')

                # Prepare the payload with sampling config
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
                                    "text": user_prompt
                                }
                            ]
                        }
                    ],
                    "temperature": self.sampling_config.get('temperature', 1.0),
                    "top_p": self.sampling_config.get('top_p', 1.0),
                    "top_k": self.sampling_config.get('top_k', 0),
                    "max_tokens": self.sampling_config.get('max_tokens', 200)
                }

                api_url = self.api_url
                if not api_url.endswith('/v1/chat/completions'):
                    api_url = api_url.rstrip('/') + '/v1/chat/completions'

                self.caption_text.setText("Generating caption...")
                
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

                            # Optionally save single image caption too
                            txt_path = os.path.splitext(self.current_image_path)[0] + '.txt'
                            with open(txt_path, 'w', encoding='utf-8') as f:
                                f.write(caption)
                        else:
                            self.caption_text.setText("No caption generated")
                    except ValueError:
                        self.caption_text.setText(f"Error: Could not parse JSON response\n{response.text}")
                else:
                    self.caption_text.setText(f"Error: {response.status_code}\n{response.text}")
                        
            except Exception as e:
                self.caption_text.setText(f"Error: {str(e)}")
                print(f"Exception details: {str(e)}")