import os
import json
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QFileDialog, QTextEdit, QMessageBox, QComboBox,
                              QDialog, QLineEdit, QFormLayout, QProgressBar, QMenuBar,
                              QMenu, QDoubleSpinBox, QSpinBox, QCheckBox, QRadioButton)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QPixmap
import requests
import base64
import asyncio
from PIL import Image
import io
from tqdm import tqdm

class BatchProcessThread(QThread):
    progress = Signal(int, int)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api_url, api_key, image_files, user_prompt, sampling_config, use_tags, prefix=""):
        super().__init__()
        self.api_url = api_url
        self.api_key = api_key
        self.image_files = image_files
        self.user_prompt = user_prompt
        self.sampling_config = sampling_config
        self.use_tags = use_tags
        self.prefix = prefix.strip()
        self.results = {}

    def run(self):
        try:
            for i, image_path in enumerate(tqdm(self.image_files, desc="Processing", ncols=70), 1):
                # Try to load tags if enabled
                prompt = self.user_prompt
                if self.use_tags:
                    try:
                        tags_path = os.path.splitext(image_path)[0] + '.txt'
                        if os.path.exists(tags_path):
                            with open(tags_path, 'r', encoding='utf-8') as f:
                                tags = f.read().strip()
                                prompt += ' Also here are booru tags for better understanding of the picture, you can use them as reference.'
                                prompt += f' <tags>\n{tags}\n</tags>'
                    except Exception as e:
                        print(f"Error loading tags for {image_path}: {str(e)}")

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
                                    "text": prompt
                                }
                            ]
                        }
                    ],
                    **self.sampling_config
                }

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
                        
                        # Add prefix to caption content if provided
                        if self.prefix:
                            caption = f"{self.prefix}\n{caption}"
                            
                        self.results[image_path] = caption

                        # Save caption file with same name as image but .caption extension
                        caption_path = os.path.splitext(image_path)[0] + '.caption'
                        with open(caption_path, 'w', encoding='utf-8') as f:
                            f.write(caption)  # Save with prefix included

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
        self.setWindowTitle("Image Caption Generator")
        self.setMinimumSize(800, 600)
        
        # Initialize class variables
        self.current_image_path = None
        self.selected_files = []
        self.is_batch_mode = False  # Initialize here
        
        # Define caption styles
        self.caption_styles = {
            "JSON Format": "Describe the picture in structured json-like format.",
            "Detailed": "Give a long and detailed description of the picture.",
            "Brief": "Describe the picture briefly."
        }
        
        # Initialize API configuration
        self.api_url = 'http://127.0.0.1:5000'
        self.api_key = ''
        self.load_config()
        
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
        
        # Create radio buttons and select button layout with prefix
        mode_layout = QHBoxLayout()
        
        # Create radio buttons
        self.single_radio = QRadioButton("Single Image")
        self.folder_radio = QRadioButton("Folder")
        self.single_radio.setChecked(True)  # Default to single image mode
        
        # Create select button
        self.select_button = QPushButton("Select Image")
        
        # Create prefix input
        prefix_label = QLabel("Prefix:")
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("Optional prefix for saved files")
        self.prefix_input.setMaximumWidth(150)  # Limit width
        
        # Add to horizontal layout
        mode_layout.addWidget(self.single_radio)
        mode_layout.addWidget(self.folder_radio)
        mode_layout.addWidget(self.select_button)
        mode_layout.addWidget(prefix_label)
        mode_layout.addWidget(self.prefix_input)
        mode_layout.addStretch()
        
        # Create checkbox for tags
        self.use_tags_checkbox = QCheckBox("Use Reference Tags")
        self.use_tags_checkbox.setToolTip("If checked, will look for matching .txt files with reference tags")
        
        self.generate_button = QPushButton("Generate Caption")
        self.generate_button.setEnabled(False)
        
        self.caption_text = QTextEdit()
        self.caption_text.setReadOnly(True)
        self.caption_text.setPlaceholderText("Generated caption will appear here...")
        
        # Add widgets to layout
        layout.addWidget(self.image_label)
        layout.addLayout(style_layout)
        layout.addLayout(mode_layout)
        layout.addWidget(self.use_tags_checkbox)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.caption_text)
        
        # Connect signals
        self.select_button.clicked.connect(self.handle_select)
        self.single_radio.toggled.connect(self.update_select_button)
        self.folder_radio.toggled.connect(self.update_select_button)
        self.generate_button.clicked.connect(self.generate_caption)
        self.use_tags_checkbox.stateChanged.connect(self.update_generate_button_state)
        self.style_combo.currentIndexChanged.connect(self.update_generate_button_state)
        
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
        self.caption_text.setText(f"Processing image {current} of {total}...")

    def batch_processing_finished(self, results):
        # Re-enable buttons
        self.select_button.setEnabled(True)
        self.generate_button.setEnabled(True)
        self.single_radio.setEnabled(True)
        self.folder_radio.setEnabled(True)

        # Show summary
        summary = f"Processed {len(results)} images.\n\nResults have been saved as .caption files next to the images."
        self.caption_text.setText(summary)

    def batch_processing_error(self, error_message):
        # Re-enable buttons
        self.select_button.setEnabled(True)
        self.generate_button.setEnabled(True)
        self.single_radio.setEnabled(True)
        self.folder_radio.setEnabled(True)

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
            base_url = self.api_url.split('/v1')[0]
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'accept': 'application/json'
            }
            
            response = requests.get(base_url, headers=headers)
            
            if response.status_code != 500:
                self.status_label.setText("Backend Status: Connected")
                self.status_label.setStyleSheet("color: green")
                self.update_generate_button_state()
            else:
                raise Exception("Backend not responding properly")
        except Exception as e:
            print(f"Backend connection error: {str(e)}")
            self.status_label.setText("Backend Status: Not Connected")
            self.status_label.setStyleSheet("color: red")
            self.generate_button.setEnabled(False)

    def select_folder(self):
        """Handle folder selection"""
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

        self.current_image_path = None
        self.caption_text.setText(f"Found {len(self.selected_files)} images. Click 'Generate Caption' to process them.")

        # Show first image as preview
        if self.selected_files:
            self.show_preview(self.selected_files[0])
        
        self.update_generate_button_state()

    def show_preview(self, image_path):
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

    def update_select_button(self):
        """Update select button text based on selected mode"""
        if self.single_radio.isChecked():
            self.select_button.setText("Select Image")
            self.is_batch_mode = False
        else:
            self.select_button.setText("Select Folder")
            self.is_batch_mode = True

    def handle_select(self):
        """Handle selection based on current mode"""
        if self.single_radio.isChecked():
            self.upload_image()
        else:
            self.select_folder()

    def upload_image(self):
        """Handle single image selection"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        
        if file_name:
            self.current_image_path = file_name
            self.selected_files = []
            self.show_preview(file_name)
            self.caption_text.clear()
            self.update_generate_button_state()

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # Create Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        # Add Sampling action
        sampling_action = settings_menu.addAction("Sampling")
        sampling_action.triggered.connect(self.show_sampling_dialog)

        # Add Configure API action
        api_config_action = settings_menu.addAction("Configure API")
        api_config_action.triggered.connect(self.show_config_dialog)

    def show_sampling_dialog(self):
        dialog = SamplingConfigDialog(self)
        if dialog.exec_():
            self.load_sampling_config()

    def load_sampling_config(self):
        """Load sampling configuration from sampling_config.json"""
        if os.path.exists('sampling_config.json'):
            with open('sampling_config.json', 'r') as f:
                self.sampling_config = json.load(f)

    def update_generate_button_state(self):
        """Update generate button state based on current conditions"""
        should_enable = False
        
        if self.is_batch_mode:
            # Enable if we have files selected for batch mode
            should_enable = len(self.selected_files) > 0
        else:
            # Enable if we have a single image selected
            should_enable = self.current_image_path is not None

        self.generate_button.setEnabled(should_enable)

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
                self.sampling_config,
                self.use_tags_checkbox.isChecked(),
                self.prefix_input.text()  # Pass the prefix
            )
            self.batch_thread.progress.connect(self.update_progress)
            self.batch_thread.finished.connect(self.batch_processing_finished)
            self.batch_thread.error.connect(self.batch_processing_error)

            # Update UI
            self.select_button.setEnabled(False)
            self.generate_button.setEnabled(False)
            self.single_radio.setEnabled(False)
            self.folder_radio.setEnabled(False)

            self.batch_thread.start()
        else:
            # Single image processing
            try:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'accept': 'application/json',
                    'Content-Type': 'application/json'
                }

                # Try to load tags if enabled
                if self.use_tags_checkbox.isChecked():
                    try:
                        tags_path = os.path.splitext(self.current_image_path)[0] + '.txt'
                        if os.path.exists(tags_path):
                            with open(tags_path, 'r', encoding='utf-8') as f:
                                tags = f.read().strip()
                                user_prompt += ' Also here are booru tags for better understanding of the picture, you can use them as reference.'
                                user_prompt += f' <tags>\n{tags}\n</tags>'
                    except Exception as e:
                        print(f"Error loading tags: {str(e)}")

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
                            
                            # Add prefix to caption content if provided
                            prefix = self.prefix_input.text().strip()
                            if prefix:
                                caption = f"{prefix}\n{caption}"
                                
                            self.caption_text.setText(caption)

                            # Save caption file with same name as image but .caption extension
                            caption_path = os.path.splitext(self.current_image_path)[0] + '.caption'
                            with open(caption_path, 'w', encoding='utf-8') as f:
                                f.write(caption)  # Save with prefix included
                        else:
                            self.caption_text.setText("No caption generated")
                    except ValueError:
                        self.caption_text.setText(f"Error: Could not parse JSON response\n{response.text}")
                else:
                    self.caption_text.setText(f"Error: {response.status_code}\n{response.text}")
                        
            except Exception as e:
                self.caption_text.setText(f"Error: {str(e)}")
                print(f"Exception details: {str(e)}")