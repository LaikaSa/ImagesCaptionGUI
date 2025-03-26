import os
import json
from pathlib import Path  # Add this import
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QFileDialog, QTextEdit, QMessageBox, QComboBox,
                              QDialog, QLineEdit, QFormLayout, QMenuBar,
                              QMenu, QDoubleSpinBox, QSpinBox, QCheckBox, QRadioButton)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QPixmap
import requests
import base64
from tqdm import tqdm
import time
from src.model_download import ModelDownloadDialog  # At the top of your file
from src.worker_thread import WorkerThread

class ModelComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def mousePressEvent(self, event):
        if self.count() == 1 and self.currentText() == "Add new model...":
            print("Empty state click detected, showing download dialog...")
            dialog = ModelDownloadDialog(self.parent)
            dialog.setWindowTitle("Download New Model")
            dialog.setModal(True)
            if dialog.exec():
                print("Model download dialog accepted")
                self.parent.refresh_models()
        else:
            super().mousePressEvent(event)

class CaptionFormatDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Caption Format Settings")
        self.setModal(True)
        self.setMinimumWidth(300)
        
        layout = QFormLayout(self)
        
        # Create input fields
        self.tags_format = QLineEdit()
        self.caption_format = QLineEdit()
        
        # Load saved settings or use defaults
        self.load_settings()
        
        # Add fields to layout
        layout.addRow("Reference Tags Format:", self.tags_format)
        layout.addRow("Caption Save Format:", self.caption_format)
        
        # Add help text
        help_text = QLabel("Enter file extensions (e.g., .txt, .caption)")
        help_text.setStyleSheet("color: gray;")
        layout.addRow(help_text)
        
        # Add save button
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        layout.addRow(save_button)
    
    def load_settings(self):
        """Load format settings from file"""
        try:
            if os.path.exists('format_config.json'):
                with open('format_config.json', 'r') as f:
                    config = json.load(f)
                    self.tags_format.setText(config.get('tags_format', '.txt'))
                    self.caption_format.setText(config.get('caption_format', '.caption'))
            else:
                # Set defaults
                self.tags_format.setText('.txt')
                self.caption_format.setText('.caption')
        except Exception as e:
            print(f"Error loading format settings: {e}")
            # Set defaults on error
            self.tags_format.setText('.txt')
            self.caption_format.setText('.caption')
    
    def save_settings(self):
        """Save format settings to file"""
        try:
            config = {
                'tags_format': self.tags_format.text().strip(),
                'caption_format': self.caption_format.text().strip()
            }
            
            # Validate formats
            for fmt in config.values():
                if not fmt.startswith('.'):
                    QMessageBox.warning(self, "Invalid Format", 
                                     "File formats must start with a dot (.)")
                    return
            
            with open('format_config.json', 'w') as f:
                json.dump(config, f)
            
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")

class BatchProcessThread(QThread):
    progress = Signal(int, int)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, **kwargs):
        super().__init__()
        self.api_url = kwargs.get('api_url')
        self.api_key = kwargs.get('api_key')
        self.image_files = kwargs.get('image_files')
        self.user_prompt = kwargs.get('user_prompt')
        self.sampling_config = kwargs.get('sampling_config')
        self.use_tags = kwargs.get('use_tags')
        self.prefix = kwargs.get('prefix', '').strip()
        self.tags_format = kwargs.get('tags_format', '.txt')
        self.caption_format = kwargs.get('caption_format', '.caption')
        self.results = {}

    def run(self):
        try:
            import os  # Add this import
            import time  # Make sure time is imported too
            
            for i, image_path in enumerate(tqdm(self.image_files, desc="Processing", ncols=70), 1):
                print(f"\nProcessing image {i}: {image_path}")  # Debug print
                
                try:
                    # Try to load tags if enabled
                    prompt = self.user_prompt
                    if self.use_tags:
                        try:
                            tags_path = os.path.splitext(image_path)[0] + self.tags_format
                            if os.path.exists(tags_path):
                                with open(tags_path, 'r', encoding='utf-8') as f:
                                    tags = f.read().strip()
                                    prompt += ' Also here are booru tags for better understanding of the picture, you can use them as reference.'
                                    prompt += f' <tags>\n{tags}\n</tags>'
                                print(f"Loaded tags for {image_path}")  # Debug print
                        except Exception as e:
                            print(f"Error loading tags for {image_path}: {str(e)}")

                    headers = {
                        'Authorization': f'Bearer {self.api_key}',
                        'accept': 'application/json',
                        'Content-Type': 'application/json',
                        'Cache-Control': 'no-cache',
                        'X-Request-ID': f'{time.time()}_{i}_{os.path.basename(image_path)}'
                    }

                    # Print image size for debugging
                    import os
                    print(f"Image size: {os.path.getsize(image_path)} bytes")

                    with open(image_path, 'rb') as img_file:
                        image_data = img_file.read()
                        image_base64 = base64.b64encode(image_data).decode('utf-8')
                        print(f"Base64 length: {len(image_base64)}")  # Debug print

                    payload = {
                        "messages": [
                            {
                                "role": "system",
                                "content": f"Processing image {i} of {len(self.image_files)}: {os.path.basename(image_path)}"
                            },
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

                    request_url = self.api_url.rstrip('/') + '/v1/chat/completions'
                    print(f"Sending request for image {i}")  # Debug print
                    
                    response = requests.post(request_url, headers=headers, json=payload)
                    print(f"Response for image {i}:")  # Debug print
                    print(f"Status: {response.status_code}")
                    print(f"Headers: {response.headers}")
                    print(f"Body: {response.text[:200]}...")  # Print first 200 chars

                    if response.status_code == 200:
                        result = response.json()
                        if 'choices' in result and len(result['choices']) > 0:
                            caption = result['choices'][0]['message']['content']
                            
                            if self.prefix:
                                caption = f"{self.prefix}\n{caption}"
                                
                            self.results[image_path] = caption

                            caption_path = os.path.splitext(image_path)[0] + self.caption_format
                            with open(caption_path, 'w', encoding='utf-8') as f:
                                f.write(caption)
                            print(f"Saved caption for image {i}")  # Debug print

                except Exception as e:
                    print(f"Error processing image {i} ({image_path}): {str(e)}")
                    continue

                self.progress.emit(i, len(self.image_files))

            print(f"Completed processing {len(self.results)} images")  # Debug print
            self.finished.emit(self.results)
        except Exception as e:
            print(f"Thread error: {str(e)}")  # Debug print
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
        
        # Create spin boxes for each parameter with smaller minimums and more decimals
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.001)  # Smaller step
        self.temperature.setDecimals(4)        # More decimal places
        
        self.top_p = QDoubleSpinBox()
        self.top_p.setRange(0.0, 1.0)
        self.top_p.setSingleStep(0.001)        # Smaller step
        self.top_p.setDecimals(4)              # More decimal places
        
        self.top_k = QSpinBox()
        self.top_k.setRange(0, 100)
        
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(1, 2000)
        
        # Add tooltips with updated information
        self.temperature.setToolTip("Controls randomness. Higher values make output more random, lower values make it more deterministic. Can be very small (e.g., 0.001)")
        self.top_p.setToolTip("Controls diversity. Lower values make output more focused. Can be very small (e.g., 0.001)")
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
        
        # Load values
        self.load_config()

    def load_config(self):
        """Load current sampling configuration"""
        # Get values from parent window's sampling_config
        config = self.parent().sampling_config
        self.temperature.setValue(config.get('temperature', 0.5))
        self.top_p.setValue(config.get('top_p', 0.5))
        self.top_k.setValue(config.get('top_k', 50))
        self.max_tokens.setValue(config.get('max_tokens', 500))
    
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
            "Brief": "Describe the picture briefly.",
            "Custom": ""  # Empty string as we'll use custom input
        }
        
        # Initialize API configuration
        self.api_url = 'http://127.0.0.1:5000'
        self.api_key = ''
        self.load_config()
        
        # Initialize sampling config from model's config or defaults
        self.sampling_config = self.get_default_sampling_config()
        self.load_sampling_config()

        # Initialize format settings
        self.tags_format = '.txt'
        self.caption_format = '.caption'
        self.load_format_settings()        

        # Create menu bar
        self.create_menu_bar()
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create model selection layout
        model_layout = QHBoxLayout()
        model_layout.addStretch()

        model_label = QLabel("Model:")
        self.model_combo = ModelComboBox(self)
        self.model_combo.setMinimumWidth(200)

        # Add load button
        self.load_model_button = QPushButton("Load")
        self.load_model_button.clicked.connect(self.load_selected_model)
        self.load_model_button.setToolTip("Load the selected model")

        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.load_model_button)

        # Add model selection to layout
        layout.addLayout(model_layout)
        
        # Initialize models
        print("Initializing models...")
        self.refresh_models()
        
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

        # Add custom prompt input
        self.custom_prompt_input = QLineEdit()
        self.custom_prompt_input.setPlaceholderText("Enter your custom prompt here...")
        self.custom_prompt_input.setMinimumWidth(200)
        self.custom_prompt_input.hide()  # Hidden by default
        style_layout.addWidget(self.custom_prompt_input)

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
        self.style_combo.currentTextChanged.connect(self.handle_style_selection) 

        self.custom_prompt_input.textChanged.connect(self.update_generate_button_state)
        
        # Initialize model combo signal
        print("Setting up model combo signal...")  # Debug print

        # Load available models
        print("Refreshing models...")  # Debug print
        self.refresh_models()
        
        # Start backend status check timer
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_backend_status)
        self.check_timer.start(5000)
        
        # Start model refresh timer
        self.model_refresh_timer = QTimer()
        self.model_refresh_timer.timeout.connect(self.refresh_model_status)
        self.model_refresh_timer.start(10000)
        
        # Initial status check
        self.check_backend_status()

    def load_selected_model(self):
        """Load the model selected in the dropdown"""
        selected_model = self.model_combo.currentText()
        
        # Don't attempt to load if it's the "Add new model..." option or separator
        if not selected_model or selected_model == "Add new model..." or selected_model.startswith("-"):
            QMessageBox.warning(self, "Invalid Selection", "Please select a valid model to load.")
            return
        
        # Disable UI during model loading
        self.model_combo.setEnabled(False)
        self.load_model_button.setEnabled(False)
        self.generate_button.setEnabled(False)
        self.status_label.setText("Loading model...")
        self.status_label.setStyleSheet("color: orange")
        
        # Create and start worker thread with keyword arguments
        self.worker = WorkerThread(
            task_func=self.switch_model_task,
            model_name=selected_model,
            api_url=self.api_url,
            api_key=self.api_key
        )
        self.worker.finished.connect(self.on_switch_complete)
        self.worker.error.connect(self.on_switch_error)
        self.worker.start()

    def switch_model_task(self, model_name, api_url, api_key):
        """Task function to switch models (to be run in a worker thread)"""
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'X-Admin-Key': api_key,
                'accept': 'application/json',
                'Content-Type': 'application/json'
            }

            # First check if a model is loaded
            health_url = api_url.rstrip('/') + '/health'
            health_response = requests.get(health_url, headers=headers)
            if health_response.status_code == 200:
                # Properly unload the current model
                print("Unloading current model...")
                unload_url = api_url.rstrip('/') + '/v1/model/unload'
                unload_response = requests.post(unload_url, headers=headers)
                print(f"Unload response: {unload_response.status_code}")
                
                # Wait for unload to complete
                import time
                time.sleep(5)

            # Load new model with vision enabled
            load_url = api_url.rstrip('/') + '/v1/model/load'
            payload = {
                "model_name": model_name,
                "vision": True
            }
            
            print(f"Loading model: {model_name} with vision enabled")
            
            # Use non-streaming request first to initiate load
            init_response = requests.post(load_url, headers=headers, json=payload)
            if init_response.status_code != 200:
                raise Exception(f"Error initiating model load: {init_response.text}")

            # Wait for model to be fully ready
            max_retries = 30  # Increased retries
            for i in range(max_retries):
                time.sleep(2)  # Wait between checks
                
                try:
                    health_response = requests.get(health_url, headers=headers)
                    if health_response.status_code == 200:
                        health_data = health_response.json()
                        if health_data.get("status") == "healthy":
                            print(f"Model verified ready after {i+1} attempts")
                            return {"status": "success", "model": model_name}
                except Exception as e:
                    print(f"Health check attempt {i+1} failed: {str(e)}")
                
                print(f"Model not ready yet, attempt {i+1} of {max_retries}")
            
            raise Exception("Model failed to become ready after maximum retries")

        except Exception as e:
            print(f"Exception in switch_model_task: {str(e)}")
            raise Exception(f"Error switching model: {str(e)}")

    def handle_style_selection(self, style):
        """Handle caption style selection changes"""
        if style == "Custom":
            self.custom_prompt_input.show()
        else:
            self.custom_prompt_input.hide()

    def refresh_models(self):
        """Get list of available models and sync with currently loaded model"""
        self.model_combo.clear()
        
        backend_path = Path("backend")
        models_path = backend_path / "models"
        
        # Create models directory if it doesn't exist
        models_path.mkdir(parents=True, exist_ok=True)
        
        # Block signals temporarily
        self.model_combo.blockSignals(True)
        
        # Get list of installed models
        models = []
        if models_path.exists():
            models = [d.name for d in models_path.iterdir() if d.is_dir()]
        
        # Add installed models if any
        if models:
            self.model_combo.addItems(models)
            self.model_combo.addItem("-" * 30)  # Separator
        
        # Always add "Add new model..." option
        self.model_combo.addItem("Add new model...")
        
        # Get currently loaded model from server
        try:
            # First try health endpoint
            health_url = self.api_url.rstrip('/') + '/health'
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'accept': 'application/json'
            }
            
            health_response = requests.get(health_url, headers=headers, timeout=5)
            current_model = None
            
            if health_response.status_code == 200:
                health_data = health_response.json()
                current_model = health_data.get('model_name')
                
                # If health endpoint doesn't provide model info, try completion endpoint
                if not current_model:
                    api_url = self.api_url.rstrip('/') + '/v1/chat/completions'
                    headers['Content-Type'] = 'application/json'
                    
                    payload = {
                        "messages": [{"role": "user", "content": "test"}],
                        "max_tokens": 1
                    }
                    
                    response = requests.post(api_url, headers=headers, json=payload, timeout=5)
                    
                    if response.status_code == 200:
                        current_model = response.json().get('model')
            
            # Set the current model in combo box if found
            if current_model:
                print(f"Server has model loaded: {current_model}")  # Debug print
                index = self.model_combo.findText(current_model)
                if index >= 0:
                    self.model_combo.setCurrentIndex(index)
                    print(f"Set combo box to loaded model: {current_model}")  # Debug print
                else:
                    print(f"Warning: Loaded model {current_model} not found in available models")
        except Exception as e:
            print(f"Error getting current model from server: {str(e)}")
        
        # Connect signal for model selection changes
        try:
            if hasattr(self, '_model_combo_connected'):
                try:
                    self.model_combo.currentTextChanged.disconnect(self.handle_model_selection)
                except TypeError:
                    pass
            self.model_combo.currentTextChanged.connect(self.handle_model_selection)
            self._model_combo_connected = True
        except Exception as e:
            print(f"Error handling model combo signals: {str(e)}")
        
        # Unblock signals
        self.model_combo.blockSignals(False)

    def handle_empty_combo_click(self, event):
        """Handle clicks on the combo box when it's empty"""
        if not any(d.is_dir() for d in (Path("backend") / "models").iterdir()):
            print("Opening download dialog from empty state...")
            dialog = ModelDownloadDialog(self)
            dialog.setWindowTitle("Download New Model")
            dialog.setModal(True)
            if dialog.exec():
                print("Model download dialog accepted")
                # Remove the custom click handler
                self.model_combo.mousePressEvent = self.model_combo.__class__.mousePressEvent
                self.refresh_models()
        # Call the original mousePressEvent
        self.model_combo.__class__.mousePressEvent(self.model_combo, event)
    
    def refresh_model_status(self):
        """Periodically check and update the current model status"""
        try:
            health_url = self.api_url.rstrip('/') + '/health'
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'accept': 'application/json'
            }
            
            response = requests.get(health_url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                health_data = response.json()
                current_model = health_data.get('model_name')
                
                if current_model:
                    index = self.model_combo.findText(current_model)
                    if index >= 0 and index != self.model_combo.currentIndex():
                        self.model_combo.blockSignals(True)
                        self.model_combo.setCurrentIndex(index)
                        self.model_combo.blockSignals(False)
                        print(f"Updated current model to: {current_model}")
        
        except Exception as e:
            print(f"Error refreshing model status: {str(e)}")

    def handle_model_selection(self, selection):
        """Handle model selection including download option"""
        print(f"handle_model_selection called with: {selection}")  # Debug print
        
        # Ignore empty selections or initial state
        if not selection:
            return
            
        if selection == "Add new model...":
            print("Opening download dialog...")  # Debug print
            try:
                dialog = ModelDownloadDialog(self)
                dialog.setWindowTitle("Download New Model")
                dialog.setModal(True)
                result = dialog.exec()
                print(f"Dialog result: {result}")  # Debug print
                
                if result:
                    print("Model download dialog accepted")
                    self.refresh_models()
                
                # Reset selection to previous model if one exists
                self.model_combo.blockSignals(True)
                if self.model_combo.count() > 1:
                    self.model_combo.setCurrentIndex(0)
                self.model_combo.blockSignals(False)
                
            except Exception as e:
                print(f"Error in handle_model_selection: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to open model download dialog: {str(e)}")
        # Remove the automatic model switching part that was here

    def switch_model(self, model_name):
        # Don't attempt to switch if model_name is empty or None
        if not model_name or model_name == "Add new model...":
            self.model_combo.setEnabled(True)
            return

        def switch_task(model_name, api_url, api_key):
            try:
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'X-Admin-Key': api_key,
                    'accept': 'application/json',
                    'Content-Type': 'application/json'
                }

                # First check if a model is loaded
                health_url = api_url.rstrip('/') + '/health'
                health_response = requests.get(health_url, headers=headers)
                if health_response.status_code == 200:
                    # Properly unload the current model
                    print("Unloading current model...")
                    unload_url = api_url.rstrip('/') + '/v1/model/unload'
                    unload_response = requests.post(unload_url, headers=headers)
                    print(f"Unload response: {unload_response.status_code}")
                    
                    # Wait for unload to complete
                    import time
                    time.sleep(5)

                # Load new model with vision enabled
                load_url = api_url.rstrip('/') + '/v1/model/load'
                payload = {
                    "model_name": model_name,
                    "vision": True
                }
                
                print(f"Loading model: {model_name} with vision enabled")
                
                # Use non-streaming request first to initiate load
                init_response = requests.post(load_url, headers=headers, json=payload)
                if init_response.status_code != 200:
                    raise Exception(f"Error initiating model load: {init_response.text}")

                # Wait for model to be fully ready
                max_retries = 30  # Increased retries
                for i in range(max_retries):
                    time.sleep(2)  # Wait between checks
                    
                    try:
                        health_response = requests.get(health_url, headers=headers)
                        if health_response.status_code == 200:
                            health_data = health_response.json()
                            if health_data.get("status") == "healthy":
                                print(f"Model verified ready after {i+1} attempts")
                                return {"status": "success", "model": model_name}
                    except Exception as e:
                        print(f"Health check attempt {i+1} failed: {str(e)}")
                    
                    print(f"Model not ready yet, attempt {i+1} of {max_retries}")
                
                raise Exception("Model failed to become ready after maximum retries")

            except Exception as e:
                print(f"Exception in switch_task: {str(e)}")
                raise Exception(f"Error switching model: {str(e)}")

        # Disable UI during model switch
        self.model_combo.setEnabled(False)
        self.generate_button.setEnabled(False)
        self.status_label.setText("Switching model...")
        self.status_label.setStyleSheet("color: orange")

        # Create and start worker thread with keyword arguments
        self.worker = WorkerThread(
            task_func=switch_task,
            model_name=model_name,
            api_url=self.api_url,
            api_key=self.api_key
        )
        self.worker.finished.connect(self.on_switch_complete)
        self.worker.error.connect(self.on_switch_error)
        self.worker.start()

    def get_current_model(self):
        """Get currently loaded model from server"""
        try:
            api_url = self.api_url.rstrip('/') + '/v1/chat/completions'
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "messages": [],
                "max_tokens": 1
            }
            
            response = requests.post(api_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                current_model = response.json().get('model')
                if current_model:
                    index = self.model_combo.findText(current_model)
                    if index >= 0:
                        self.model_combo.blockSignals(True)
                        self.model_combo.setCurrentIndex(index)
                        self.model_combo.blockSignals(False)
        except Exception as e:
            print(f"Error getting current model: {str(e)}")

    def on_switch_complete(self, result):
        print(f"Model switch completed successfully: {result}")
        self.model_combo.setEnabled(True)
        self.status_label.setText("Model loaded successfully")
        self.status_label.setStyleSheet("color: green")
        self.update_generate_button_state()

    def on_switch_error(self, error_msg):
        print(f"Error switching model: {error_msg}")
        self.model_combo.setEnabled(True)
        self.status_label.setText(f"Error: {error_msg}")
        self.status_label.setStyleSheet("color: red")
        self.get_current_model()

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

    def load_format_settings(self):
        """Load format settings from config file"""
        try:
            if os.path.exists('format_config.json'):
                with open('format_config.json', 'r') as f:
                    config = json.load(f)
                    self.tags_format = config.get('tags_format', '.txt')
                    self.caption_format = config.get('caption_format', '.caption')
        except Exception as e:
            print(f"Error loading format settings: {e}")

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
        
        # Add Caption Format action
        format_action = settings_menu.addAction("Caption Format")
        format_action.triggered.connect(self.show_format_dialog)

    def show_format_dialog(self):
        """Show the caption format configuration dialog"""
        dialog = CaptionFormatDialog(self)
        if dialog.exec_():
            # Reload format settings
            self.load_format_settings()

    def show_sampling_dialog(self):
        dialog = SamplingConfigDialog(self)
        if dialog.exec_():
            self.load_sampling_config()

    def get_default_sampling_config(self):
        """Get sampling config from model's generation_config.json if it exists"""
        try:
            # Look for generation_config.json in the backend/models directory
            backend_path = Path("backend")
            models_path = backend_path / "models"
            
            # Get first model directory (assuming it's the active one)
            model_dirs = [d for d in models_path.iterdir() if d.is_dir()]
            if model_dirs:
                config_path = model_dirs[0] / "generation_config.json"
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        return {
                            'temperature': config.get('temperature', 0.5),
                            'top_p': config.get('top_p', 0.5),
                            'top_k': config.get('top_k', 50),
                            'max_tokens': 500  # This usually isn't in generation_config.json
                        }
        except Exception as e:
            print(f"Error loading generation_config.json: {e}")
        
        # Fallback to default values if no config found or error occurs
        return {
            'temperature': 0.5,
            'top_p': 0.5,
            'top_k': 50,
            'max_tokens': 500
        }

    def load_sampling_config(self):
        """Load sampling configuration from sampling_config.json if it exists"""
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

        # Verify model is loaded before proceeding
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            test_url = self.api_url.rstrip('/') + '/v1/chat/completions'
            test_payload = {
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1
            }
            
            test_response = requests.post(test_url, headers=headers, json=test_payload)
            if test_response.status_code != 200:
                QMessageBox.warning(self, "Model Not Ready", 
                                "The model is not ready. Please wait a moment and try again.")
                return
        except Exception as e:
            QMessageBox.warning(self, "Error", 
                            f"Could not verify model status: {str(e)}")
            return

        selected_style = self.style_combo.currentText()
        if selected_style == "Custom":
            user_prompt = self.custom_prompt_input.text().strip()
            if not user_prompt:
                QMessageBox.warning(self, "Input Required", 
                                "Please enter a custom prompt.")
                return
        else:
            user_prompt = self.caption_styles[selected_style]

        # Check if current model is ExLlamaV2
        current_model = self.model_combo.currentText()
        is_exl2 = "exl2" in current_model.lower()

        # Use greedy sampling for ExLlamaV2 models
        if is_exl2:
            sampling_config = {
                'temperature': 1.0,
                'top_k': 1,
                'top_p': 1.0,
                'typical': 1.0,
                'min_p': 0.0,
                'mirostat': False,
                'smoothing_factor': 0.0,
                'tfs': 1.0,
                'temperature_last': False,
                'token_repetition_penalty': 1.0,
                'token_frequency_penalty': 0.0,
                'token_presence_penalty': 0.0,
                'max_tokens': self.sampling_config.get('max_tokens', 500)
            }
        else:
            sampling_config = self.sampling_config

        if self.is_batch_mode and self.selected_files:
            def batch_task(files, api_url, api_key, prompt, sampling_config, use_tags, prefix):
                results = {}
                for i, image_path in enumerate(tqdm(files, desc="Processing", ncols=70), 1):
                    try:
                        # Try to load tags if enabled
                        current_prompt = prompt
                        if use_tags:
                            try:
                                tags_path = os.path.splitext(image_path)[0] + '.txt'
                                if os.path.exists(tags_path):
                                    with open(tags_path, 'r', encoding='utf-8') as f:
                                        tags = f.read().strip()
                                        current_prompt += ' Also here are booru tags for better understanding of the picture, you can use them as reference.'
                                        current_prompt += f' <tags>\n{tags}\n</tags>'
                            except Exception as e:
                                print(f"Error loading tags for {image_path}: {str(e)}")

                        headers = {
                            'Authorization': f'Bearer {api_key}',
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
                                            "text": f"{current_prompt} [Request: {time.time()}]"  # Add timestamp
                                        }
                                    ]
                                }
                            ],
                            **sampling_config
                        }

                        request_url = api_url.rstrip('/') + '/v1/chat/completions'
                        response = requests.post(request_url, headers=headers, json=payload)

                        if response.status_code == 200:
                            result = response.json()
                            if 'choices' in result and len(result['choices']) > 0:
                                caption = result['choices'][0]['message']['content']
                                
                                # Add prefix to caption content if provided
                                if prefix:
                                    caption = f"{prefix}\n{caption}"
                                    
                                results[image_path] = caption

                                # Save caption file with same name as image but .caption extension
                                caption_path = os.path.splitext(image_path)[0] + '.caption'
                                with open(caption_path, 'w', encoding='utf-8') as f:
                                    f.write(caption)

                    except Exception as e:
                        print(f"Error processing {image_path}: {str(e)}")
                        continue

                return results

            # Disable UI elements
            self.select_button.setEnabled(False)
            self.generate_button.setEnabled(False)
            self.single_radio.setEnabled(False)
            self.folder_radio.setEnabled(False)

            # Create and start worker thread with corrected argument order
            self.worker = BatchProcessThread(
                api_url=self.api_url,
                api_key=self.api_key,
                image_files=self.selected_files,
                user_prompt=user_prompt,
                sampling_config=sampling_config,
                use_tags=self.use_tags_checkbox.isChecked(),
                prefix=self.prefix_input.text(),
                tags_format=self.tags_format,  # Add this
                caption_format=self.caption_format  # Add this
            )
            self.worker.finished.connect(self.batch_processing_finished)
            self.worker.error.connect(self.batch_processing_error)
            self.worker.start()
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

                if self.use_tags_checkbox.isChecked():
                    try:
                        tags_path = os.path.splitext(self.current_image_path)[0] + self.tags_format
                        if os.path.exists(tags_path):
                            with open(tags_path, 'r', encoding='utf-8') as f:
                                tags = f.read().strip()
                                user_prompt += ' Also here are booru tags for better understanding of the picture, you can use them as reference.'
                                user_prompt += f' <tags>\n{tags}\n</tags>'
                    except Exception as e:
                        print(f"Error loading tags: {str(e)}")

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
                                    "text": f"{user_prompt} [Request: {time.time()}]"  # Add timestamp
                                }
                            ]
                        }
                    ],
                    **sampling_config
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

                            # Use the configured caption format
                            caption_path = os.path.splitext(self.current_image_path)[0] + self.caption_format
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

    def update_generate_button_state(self):
        """Update generate button state based on current conditions"""
        should_enable = False
        
        if self.is_batch_mode:
            # Enable if we have files selected for batch mode
            should_enable = len(self.selected_files) > 0
        else:
            # Enable if we have a single image selected
            should_enable = self.current_image_path is not None

        # Add custom prompt validation
        if should_enable and self.style_combo.currentText() == "Custom":
            should_enable = bool(self.custom_prompt_input.text().strip())

        self.generate_button.setEnabled(should_enable)