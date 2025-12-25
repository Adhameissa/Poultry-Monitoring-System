# Poultry Monitoring System

![Poultry Monitoring System](assets/main-banner.jpeg)

A comprehensive AI-powered solution for monitoring and managing poultry health, including disease detection, weight estimation, and farm management.

## 📸 Sample Outputs

### Disease Detection
![Disease Detection](assets/diseaseexample.jpeg)

### Weight Estimation
![Weight Estimation](assets/weightexample.jpeg)

### Poultry Dashboard
![Dashboard](assets/countexample.jpeg)


## 🌟 Features

- **Disease Detection**: AI-powered detection of common poultry diseases including:
  - Bumblefoot
  - Fowlpox
  - Coryza
  - Chronic Respiratory Disease (CRD)
  - Coccidiosis
  - Newcastle Disease
  - Salmonella

- **Weight Estimation**: Computer vision-based broiler weight estimation
- **Multi-modal Analysis**: Support for both image and video analysis
- **Multi-language Support**: Interface available in English and Arabic
- **Responsive Web Interface**: Built with Flask for the backend and modern web technologies

## 🛠️ Technical Stack

### Backend
- **Framework**: Python Flask
- **AI/ML**: 
  - PyTorch for deep learning models
  - YOLOv8 for object detection and segmentation
  - EfficientNetB3 for disease classification
  - Custom CNN models for specialized tasks

### Frontend (Web)
- HTML5, CSS3, JavaScript
- Chart.js for data visualization
- Responsive design for all devices


## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- PyTorch
- Flask
- OpenCV
- Ultralytics (YOLOv8)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Adhameissa/Poultry-Monitoring-System.git
   cd Poultry-Monitoring-System
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Download model weights**
   - Place the following model files in the project root:
     - `best.pt` (YOLOv8 detection model)
     - `bestweight.pt` (Weight estimation model)
     - `best_broiler_model.pth` (Broiler disease classification model)
     - `efficientnetb3-Chicken_Disease-95.66.pth` (Fecal disease classification model)

5. **Run the Flask application**
   ```bash
   python app.py
   ```
   The web interface will be available at `http://localhost:5000`


## 📊 Project Structure

```
Poultry-Monitoring-System/
├── app.py                 # Main Flask application
├── best.pt               # YOLOv8 detection model
├── bestweight.pt         # Weight estimation model
├── best_broiler_model.pth # Broiler disease classification model
├── efficientnetb3-Chicken_Disease-95.66.pth  # Fecal disease classification model
├── data.yaml             # Configuration file for YOLO models
├── predict_broiler_fixed.py  # Broiler disease prediction module
├── static/               # Static files (CSS, JS, images)
├── templates/            # HTML templates
├── uploads/              # Temporary storage for uploaded files
├── outputs/              # Output files (results, processed images)
```

## 📝 Usage

### Web Interface
1. Access the web interface at `http://localhost:5000`
2. Upload images or videos for analysis
3. View detailed reports and visualizations
4. Access historical data and analytics

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Contact

For any inquiries, please contact the project maintainers.

## 🙏 Acknowledgments

- YOLOv8 by Ultralytics
- PyTorch community
- All open-source libraries used in this project
