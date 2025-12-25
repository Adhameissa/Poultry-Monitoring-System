import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import numpy as np
import os
import json

class BroilerDiseaseClassifier(nn.Module):
    def __init__(self, num_classes=5, pretrained=True):
        super(BroilerDiseaseClassifier, self).__init__()
        self.backbone = models.resnet18(weights='IMAGENET1K_V1' if pretrained else None)
        in_features = self.backbone.fc.in_features
        
        self.backbone.fc = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(in_features, 512),
            nn.ReLU(inplace=True),
            nn.BatchNorm1d(512),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes)
        )

    def forward(self, x):
        return self.backbone(x)

class BroilerDiseasePredictor:
    def __init__(self, model_path="best_broiler_model.pth"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"✅ Using device: {self.device}")
        
        self.model = self.load_model(model_path)
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        
    def load_model(self, model_path):
        """Load the trained model with correct architecture"""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
            
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)
        
        # Create the exact same architecture as during training
        model = BroilerDiseaseClassifier(num_classes=len(checkpoint['class_names']), pretrained=False)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.to(self.device)
        model.eval()
        
        self.class_names = checkpoint['class_names']
        self.class_to_idx = checkpoint['class_to_idx']
        
        print(f"✅ Model loaded successfully!")
        print(f"📊 Classes: {self.class_names}")
        print(f"🎯 Number of classes: {len(self.class_names)}")
        
        return model
    
    def predict(self, image_path):
        """Predict disease from image"""
        try:
            if not os.path.exists(image_path):
                return {
                    'predicted_class': 'Error',
                    'confidence': 0.0,
                    'error': f"Image file not found: {image_path}",
                    'status': 'error'
                }
            
            # Load and preprocess image
            image = Image.open(image_path).convert("RGB")
            image_tensor = self.transform(image).unsqueeze(0).to(self.device)
            
            # Predict
            with torch.no_grad():
                outputs = self.model(image_tensor)
                probabilities = torch.nn.functional.softmax(outputs, dim=1)
                confidence, predicted_idx = torch.max(probabilities, 1)
                
            predicted_class = self.class_names[predicted_idx.item()]
            confidence_score = confidence.item()
            
            # Get all class probabilities
            all_probs = {self.class_names[i]: float(prob) 
                        for i, prob in enumerate(probabilities.cpu().numpy()[0])}
            
            return {
                'predicted_class': predicted_class,
                'confidence': confidence_score,
                'all_probabilities': all_probs,
                'status': 'success'
            }
            
        except Exception as e:
            return {
                'predicted_class': 'Error',
                'confidence': 0.0,
                'error': str(e),
                'status': 'error'
            }
    
    def predict_batch(self, image_folder):
        """Predict all images in a folder"""
        if not os.path.exists(image_folder):
            return {"error": f"Folder not found: {image_folder}"}
            
        results = {}
        image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff')
        valid_images = [f for f in os.listdir(image_folder) 
                       if f.lower().endswith(image_extensions)]
        
        print(f"🔍 Found {len(valid_images)} images in {image_folder}")
        
        for filename in valid_images:
            image_path = os.path.join(image_folder, filename)
            results[filename] = self.predict(image_path)
                
        return results

    def print_prediction(self, result, image_name=""):
        """Print formatted prediction result"""
        if result['status'] == 'success':
            print(f"\n🎯 PREDICTION RESULT:")
            if image_name:
                print(f"   Image: {image_name}")
            print(f"   Predicted: {result['predicted_class']}")
            print(f"   Confidence: {result['confidence']:.2%}")
            print(f"   All probabilities:")
            for class_name, prob in result['all_probabilities'].items():
                print(f"     - {class_name}: {prob:.2%}")
        else:
            print(f"❌ ERROR: {result.get('error', 'Unknown error')}")

# Usage examples
if __name__ == "__main__":
    # Initialize predictor
    predictor = BroilerDiseasePredictor("best_broiler_model.pth")
    
    # Test single image
    print("\n" + "="*50)
    print("🧪 SINGLE IMAGE PREDICTION TEST")
    print("="*50)
    
    # Try to find a test image automatically
    test_dirs = ["test", "valid", "train"]
    test_image_found = False
    
    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            for class_name in predictor.class_names:
                class_dir = os.path.join(test_dir, class_name)
                if os.path.exists(class_dir):
                    images = [f for f in os.listdir(class_dir) 
                             if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                    if images:
                        test_image = os.path.join(class_dir, images[0])
                        result = predictor.predict(test_image)
                        predictor.print_prediction(result, images[0])
                        test_image_found = True
                        break
            if test_image_found:
                break
    
    if not test_image_found:
        print("❌ No test images found. Please provide an image path.")
        test_image_path = input("Enter path to image: ").strip().strip('"')
        if os.path.exists(test_image_path):
            result = predictor.predict(test_image_path)
            predictor.print_prediction(result, os.path.basename(test_image_path))
        else:
            print("❌ Image path does not exist.")
    
    # Batch prediction example
    print("\n" + "="*50)
    print("📊 BATCH PREDICTION TEST")
    print("="*50)
    
    test_folder = "test"  # Change this to your test folder
    if os.path.exists(test_folder):
        batch_results = predictor.predict_batch(test_folder)
        
        success_count = sum(1 for r in batch_results.values() if r['status'] == 'success')
        print(f"📈 Batch prediction completed: {success_count}/{len(batch_results)} successful")
        
        # Show top predictions
        print(f"\n🏆 TOP PREDICTIONS:")
        for filename, result in list(batch_results.items())[:5]:  # Show first 5
            if result['status'] == 'success':
                print(f"   {filename}: {result['predicted_class']} ({result['confidence']:.2%})")
    else:
        print(f"❌ Test folder '{test_folder}' not found for batch prediction.")