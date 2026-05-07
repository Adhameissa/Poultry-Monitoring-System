from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass
from werkzeug.utils import secure_filename
import cv2
from ultralytics import YOLO
import numpy as np
from scipy.ndimage import gaussian_filter
import matplotlib.pyplot as plt
import uuid
from PIL import Image, ImageDraw, ImageFont
import mimetypes
import json
import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
import json
import torchvision.transforms as T
import torch.nn.functional as F
from financial.routes import financial_bp
from chatbot_routes import chatbot_bp

app = Flask(__name__)
CORS(app)

# Register blueprints
app.register_blueprint(financial_bp, url_prefix="/financial")
app.register_blueprint(chatbot_bp, url_prefix="/api")

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Load YOLO model
try:
    model = YOLO('best.pt')
    print("✅ YOLO model loaded successfully!")
except Exception as e:
    print(f"❌ Error loading YOLO model: {e}")
    model = None

# Load Weight Estimation YOLO model
try:
    weight_model = YOLO('bestweight.pt')
    print("✅ Weight estimation model loaded successfully!")
except Exception as e:
    print(f"❌ Error loading weight estimation model: {e}")
    weight_model = None

# Disease classes (from your model - exact order)
DISEASE_CLASSES = ['Bumblefoot', 'Fowlpox', 'Healthy', 'coryza', 'crd']
DISEASE_INFO = {
    'Bumblefoot': {
        'name': 'Bumblefoot',
        'name_ar': 'التهاب القدم',
        'description': 'Bacterial infection causing swelling and lesions on chicken feet',
        'description_ar': 'عدوى بكتيرية تسبب تورم وتقرحات في أقدام الدجاج',
        'symptoms': ['Swollen foot', 'Lameness', 'Lesions on footpad', 'Difficulty walking'],
        'symptoms_ar': ['تورم القدم', 'عرج', 'تقرحات في باطن القدم', 'صعوبة في المشي'],
        'treatment': ['Antibiotics', 'Foot soaks', 'Surgical drainage if severe', 'Improve coop cleanliness'],
        'treatment_ar': ['المضادات الحيوية', 'نقع القدم', 'تصريف جراحي في الحالات الشديدة', 'تحسين نظافة الحظيرة']
    },
    'coryza': {
        'name': 'Infectious Coryza',
        'name_ar': 'الزكام المعدي / الكوريزا',
        'description': 'Respiratory disease caused by Avibacterium paragallinarum bacteria',
        'description_ar': 'مرض تنفسي تسببه بكتيريا Avibacterium paragallinarum',
        'causative_agent': 'Avibacterium paragallinarum',
        'causative_agent_ar': 'بكتيريا Avibacterium paragallinarum',
        'age_at_risk': 'All ages',
        'age_at_risk_ar': 'جميع الأعمار',
        'symptoms': ['Facial swelling', 'Swelling around eyes', 'Nasal discharge', 'Eye discharge', 'Sneezing', 'Foul-smelling droppings'],
        'symptoms_ar': ['تورم الوجه وحول العين', 'إفرازات أنفية وعينية', 'عطس', 'رائحة كريهة للبراز'],
        'lesions': 'Sinusitis, mucous material in respiratory tract',
        'lesions_ar': 'التهاب الجيوب الأنفية، مواد مخاطية في المجاري التنفسية',
        'treatment': [
            {'name': 'Erythromycin', 'dose': '250-500 mg/1000L water', 'duration': '3-5 days'},
            {'name': 'Tylosin', 'dose': '0.5 g/L water', 'duration': '3-5 days'},
            {'name': 'Doxycycline', 'dose': '100-200 g/200L water', 'duration': '3-5 days'},
            {'name': 'Oxytetracycline', 'dose': '100 g/200L water', 'duration': '3-5 days'},
            {'name': 'Sulfa-Trimethoprim', 'dose': '1-2 mg/kg body weight', 'duration': '3-5 days'}
        ],
        'treatment_ar': [
            {'name': 'الإيزرومايسين', 'dose': '250-500 ملغ/1000 لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'تابلوزين', 'dose': '0.5 جم/لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'دوكسيسيكلين', 'dose': '100-200 جم/200 لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'أوكسيتراسيكلين', 'dose': '100 جم/200 لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'سلفا-تريميثوبريم', 'dose': '1-2 ملغ/كغ وزن', 'duration': '3-5 أيام'}
        ],
        'prevention': ['Vaccination', 'Isolation of infected birds', 'Good ventilation', 'Biosecurity measures'],
        'prevention_ar': ['التحصين', 'عزل الطيور المصابة', 'تهوية جيدة', 'إجراءات الأمن الحيوي']
    },
    'crd': {
        'name': 'Chronic Respiratory Disease',
        'name_ar': 'مرض الجهاز التنفسي المزمن',
        'description': 'Long-term respiratory infection',
        'description_ar': 'عدوى تنفسية طويلة الأمد',
        'symptoms': ['Coughing', 'Sneezing', 'Nasal discharge', 'Reduced appetite'],
        'symptoms_ar': ['سعال', 'عطس', 'إفرازات أنفية', 'فقدان الشهية'],
        'treatment': ['Antibiotics', 'Improve air quality', 'Reduce stress', 'Nutritional support'],
        'treatment_ar': ['المضادات الحيوية', 'تحسين جودة الهواء', 'تقليل الإجهاد', 'دعم غذائي']
    },
    'Fowlpox': {
        'name': 'Fowlpox',
        'name_ar': 'جدري الطيور',
        'description': 'Viral disease caused by Poxviridae virus, causing skin lesions',
        'description_ar': 'مرض فيروسي تسببه فيروسات Poxviridae، يسبب آفات جلدية',
        'causative_agent': 'Poxviridae virus',
        'causative_agent_ar': 'فيروس Poxviridae',
        'symptoms': ['Pustules on face', 'Pustules on wattles', 'Pustules around vent', 'Wart-like lesions', 'Scabs on comb/wattle', 'Reduced egg production', 'Lethargy'],
        'symptoms_ar': ['بثور على الوجه', 'بثور على الدلايات', 'بثور حول فتحة المجمع'],
        'lesions': 'Fibrinous pustules in mouth and trachea',
        'lesions_ar': 'بثور فيبرينية في الفم والقصبة الهوائية',
        'treatment': [
            {'name': 'Supportive care', 'description': 'High-dose vitamins and supportive treatment'},
            {'name': 'Oxytetracycline', 'dose': '40 g/200L water', 'duration': '3-5 days'},
            {'name': 'Isolation', 'description': 'Separate infected birds'},
            {'name': 'Vaccination', 'description': 'Vaccinate at 4-6 weeks of age by wing web puncture'}
        ],
        'treatment_ar': [
            {'name': 'العلاج الداعم', 'description': 'فيتامينات عالية الجرعة'},
            {'name': 'أوكسيتتراسيكلين', 'dose': '40 جم/200 لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'العزل', 'description': 'فصل الطيور المصابة'},
            {'name': 'التحصين', 'description': 'بالوخز في عمر 4-6 أسابيع'}
        ],
        'prevention': ['Vaccination at 4-6 weeks', 'Isolation of infected birds', 'Clean environment', 'Biosecurity'],
        'prevention_ar': ['التحصين بالوخز في عمر 4-6 أسابيع', 'عزل الطيور المصابة', 'بيئة نظيفة', 'الأمن الحيوي']
    },
    'Healthy': {
        'name': 'Healthy',
        'name_ar': 'صحي',
        'description': 'No signs of disease detected',
        'description_ar': 'لم يتم اكتشاف أي علامات للمرض',
        'symptoms': ['Normal behavior', 'Good appetite', 'Active movement', 'Bright eyes'],
        'symptoms_ar': ['سلوك طبيعي', 'شهية جيدة', 'حركة نشطة', 'عيون لامعة'],
        'treatment': ['Maintain current care', 'Regular health checks', 'Proper nutrition', 'Clean environment'],
        'treatment_ar': ['الحفاظ على الرعاية الحالية', 'فحوصات صحية منتظمة', 'تغذية مناسبة', 'بيئة نظيفة']
    }
}

# Fecal Disease classes
FECAL_CLASSES = ['Coccidiosis', 'Healthy', 'New Castle Disease', 'Salmonella']
FECAL_INFO = {
    'Coccidiosis': {
        'name': 'Coccidiosis',
        'name_ar': 'الكوكسيديا',
        'description': 'Parasitic disease of the intestinal tract caused by Eimeria spp. protozoa',
        'description_ar': 'مرض طفيلي في القناة الهضمية تسببه طفيليات Eimeria spp.',
        'causative_agent': 'Eimeria spp. parasites',
        'causative_agent_ar': 'طفيليات Eimeria spp.',
        'symptoms': ['Bloody diarrhea', 'Pale comb', 'Pale appearance', 'Weakness', 'Loss of appetite'],
        'symptoms_ar': ['إسهال دموي', 'شحوب وضعف', 'فقدان الشهية'],
        'lesions': 'Inflammation and enlargement of ceca, intestinal bleeding',
        'lesions_ar': 'التهابات وتضخم في الأعورين، نزيف معوي',
        'treatment': [
            {'name': 'Sulfa + Amprolium + Vitamins', 'dose': '0.5 g of each/L water', 'duration': '3-5 days'},
            {'name': 'Sulfaquinoxaline', 'dose': '0.5-1 g/L water', 'duration': '3-5 days'},
            {'name': 'Toltrazuril', 'dose': '200 ml/200L water', 'duration': '2 days'},
            {'name': 'Amprolium', 'dose': '0.5-1 mg/kg body weight', 'duration': '5-7 days'},
            {'name': 'Vitacox', 'dose': '1 g/L water', 'duration': '3-5 days'},
            {'name': 'Neocox', 'dose': '2 g/L water', 'duration': '3-5 days'}
        ],
        'treatment_ar': [
            {'name': 'سلفا + أمبروليوم + فيتامينات', 'dose': '0.5 جم من كل/لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'سلفاكينوكسالين', 'dose': '0.5-1 جم/لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'تولترازوريل', 'dose': '200 مل/200 لتر ماء', 'duration': 'يومين'},
            {'name': 'أمبروليوم', 'dose': '0.5-1 ملغ/كغ وزن', 'duration': '5-7 أيام'},
            {'name': 'فيتاكيكس', 'dose': '1 جم/لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'نيوكوكس', 'dose': '2 جم/لتر ماء', 'duration': '3-5 أيام'}
        ],
        'prevention': ['Good hygiene practices', 'Proper litter management', 'Vaccination programs', 'Adequate spacing', 'Proper ventilation'],
        'prevention_ar': ['ممارسات النظافة الجيدة', 'إدارة القمامة المناسبة', 'برامج التحصين', 'مسافات كافية', 'تهوية مناسبة']
    },
    'Healthy': {
        'name': 'Healthy',
        'name_ar': 'صحي',
        'description': 'No signs of disease detected in fecal matter',
        'description_ar': 'لم يتم اكتشاف أي علامات للمرض في البراز',
        'symptoms': ['Normal droppings', 'Good appetite', 'Active behavior', 'Normal egg production'],
        'symptoms_ar': ['براز طبيعي', 'شهية جيدة', 'سلوك نشط', 'إنتاج بيض طبيعي'],
        'treatment': ['Maintain current care', 'Regular monitoring', 'Proper nutrition'],
        'treatment_ar': ['الحفاظ على الرعاية الحالية', 'مراقبة منتظمة', 'تغذية مناسبة'],
        'prevention': ['Continue current practices'],
        'prevention_ar': ['مواصلة الممارسات الحالية']
    },
    'New Castle Disease': {
        'name': 'Newcastle Disease',
        'name_ar': 'مرض النيوكاسل',
        'description': 'Highly contagious viral disease caused by Paramyxoviridae virus affecting respiratory, nervous, and digestive systems',
        'description_ar': 'مرض فيروسي شديد العدوى تسببه فيروسات Paramyxoviridae يؤثر على الجهاز التنفسي والعصبي والهضمي',
        'causative_agent': 'Paramyxoviridae virus',
        'causative_agent_ar': 'فيروس Paramyxoviridae',
        'symptoms': ['Emaciation and pallor', 'Neurological movements (neck twisting)', 'Dark green diarrhea', 'Breathing difficulty'],
        'symptoms_ar': ['هزال وشحوب', 'حركات عصبية (التواء الرقبة)', 'إسهال أخضر داكن', 'صعوبة تنفس'],
        'lesions': 'Bleeding in trachea, damage to digestive tract',
        'lesions_ar': 'نزيف في القصبة الهوائية، تلف في القناة الهضمية',
        'treatment': [
            {'name': 'Vaccination', 'description': 'LaSota or Clone 30 by spray', 'dose': '0.5-1 ml/L water'},
            {'name': 'Vitamin D3', 'dose': '2 ml/2L water'},
            {'name': 'Vitamin K3', 'dose': '0.5 ml/2L water'},
            {'name': 'Disinfection', 'description': 'Daily spraying of disinfectants'}
        ],
        'treatment_ar': [
            {'name': 'التحصين', 'description': 'اللازوتا أو كولون 30 بالرش', 'dose': '0.5-1 مل/لتر ماء'},
            {'name': 'فيتامين D3', 'dose': '2 مل/2 لتر ماء'},
            {'name': 'فيتامين K3', 'dose': '0.5 مل/2 لتر ماء'},
            {'name': 'التعقيم', 'description': 'رش المطهرات يومياً'}
        ],
        'prevention': ['Regular vaccination programs', 'Strict biosecurity', 'Quarantine new birds', 'Daily disinfection'],
        'prevention_ar': ['برامج التحصين المنتظمة', 'الأمن الحيوي الصارم', 'حجر الطيور الجديدة', 'التعقيم اليومي']
    },
    'Salmonella': {
        'name': 'Salmonellosis',
        'name_ar': 'السالمونيلا',
        'description': 'Bacterial infection caused by Salmonella spp. causing gastrointestinal distress',
        'description_ar': 'عدوى بكتيرية تسببها بكتيريا السالمونيلا (Salmonella spp.) تسبب اضطرابات معوية',
        'causative_agent': 'Salmonella spp. bacteria',
        'causative_agent_ar': 'بكتيريا السالمونيلا (Salmonella spp.)',
        'infection_sources': [
            'Environmental contamination (waste, soil, water)',
            'Contaminated feed',
            'Poor breeding conditions (overcrowding, poor ventilation)',
            'Stress (transport, sudden feed change)'
        ],
        'infection_sources_ar': [
            'تلوث بيئي (مخلفات، تربة، ماء)',
            'العلف الملوث',
            'سوء ظروف التربية (ازدحام، تهوية رديئة)',
            'الإجهاد (نقل، تغيير مفاجئ في العلف)'
        ],
        'age_at_risk': 'From 1 day to 4 weeks old (most common)',
        'age_at_risk_ar': 'من عمر يوم حتى 4 أسابيع (الأكثر شيوعاً)',
        'symptoms': ['Lethargy and general weakness', 'Loss of appetite', 'Behavioral changes', 'Breathing difficulty or cough', 'Diarrhea (sometimes watery or mucous)', 'Birds gathering near heat sources'],
        'symptoms_ar': ['خمول وضعف عام', 'فقدان الشهية', 'تغير في السلوك', 'صعوبة في التنفس أو سعال', 'إسهال (أحياناً مائي أو مخاطي)', 'تجمع الطيور بالقرب من مصادر الحرارة'],
        'lesions': 'Inflammation and bleeding in intestines, enlarged liver and spleen, white spots on liver (in some types)',
        'lesions_ar': 'التهابات ونزيف في الأمعاء، تضخم الكبد والطحال، وجود بقع بيضاء على الكبد (في بعض الأنواع)',
        'droppings': 'Watery yellow-white diarrhea, may be mucous or bloody in severe cases',
        'droppings_ar': 'إسهال مائي أصفر-أبيض، قد يكون مخاطياً أو دموياً في الحالات الشديدة',
        'treatment': [
            {'name': 'Florfenicol', 'method': 'Drinking water', 'dose': '10-20 mg/kg body weight', 'duration': '3-5 days'},
            {'name': 'Colistin Sulfate', 'method': 'Drinking water', 'dose': '50,000-100,000 units/L water', 'duration': '3-5 days'},
            {'name': 'Fluoroquinolones', 'method': 'Drinking water', 'dose': '10-20 mg/L water', 'duration': '3-5 days'},
            {'name': 'Neomycin Sulfate', 'method': 'Drinking water', 'dose': '35-70 mg/L water', 'duration': '5-7 days'},
            {'name': 'Amoxicillin', 'method': 'Drinking water', 'dose': '20-40 mg/L water', 'duration': '3-5 days'},
            {'name': 'Norfloxacin', 'method': 'Drinking water', 'dose': '10-20 mg/L water', 'duration': '3-5 days'},
            {'name': 'Enrofloxacin', 'method': 'Drinking water', 'dose': '10 mg/L water', 'duration': '3-5 days'},
            {'name': 'Ciprofloxacin', 'method': 'Drinking water', 'dose': '10-20 mg/L water', 'duration': '3-5 days'},
            {'name': 'Eramycin', 'method': 'Drinking water', 'dose': '10-20 mg/L water', 'duration': '3-5 days'},
            {'name': 'Sulfadiazine + Trimethoprim', 'method': 'Drinking water', 'dose': '30 mg sulfa + 6 mg trimethoprim/L', 'duration': '3-5 days'},
            {'name': 'Fosfomycin', 'method': 'Drinking water', 'dose': '0.5-1 g/L water', 'duration': '3-5 days'}
        ],
        'treatment_ar': [
            {'name': 'فلورفينيكول', 'method': 'ماء الشرب', 'dose': '10-20 ملغ/كغ وزن حي', 'duration': '3-5 أيام'},
            {'name': 'كوليستين سلفات', 'method': 'ماء الشرب', 'dose': '50,000-100,000 وحدة/لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'فلوروكوينولونات', 'method': 'ماء الشرب', 'dose': '10-20 ملغ/لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'نيوميسين سلفات', 'method': 'ماء الشرب', 'dose': '35-70 ملغ/لتر ماء', 'duration': '5-7 أيام'},
            {'name': 'أموكسيسيلين', 'method': 'ماء الشرب', 'dose': '20-40 ملغ/لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'نورفلوكساسين', 'method': 'ماء الشرب', 'dose': '10-20 ملغ/لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'إنروفلوكساسين', 'method': 'ماء الشرب', 'dose': '10 ملغ/لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'سيبروفلوكساسين', 'method': 'ماء الشرب', 'dose': '10-20 ملغ/لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'إيراميسين', 'method': 'ماء الشرب', 'dose': '10-20 ملغ/لتر ماء', 'duration': '3-5 أيام'},
            {'name': 'سلفاديازين + تريميثوبريم', 'method': 'ماء الشرب', 'dose': '30 ملغ سلفا + 6 ملغ تريميثوبريم/لتر', 'duration': '3-5 أيام'},
            {'name': 'فوسفوميسين', 'method': 'ماء الشرب', 'dose': '0.5-1 جم/لتر ماء', 'duration': '3-5 أيام'}
        ],
        'prevention': [
            'Improve environmental conditions (ventilation, appropriate density)',
            'Use good quality feed',
            'Vaccination program against Salmonella',
            'Regular disinfection of coops and equipment',
            'Proper sanitation',
            'Rodent control',
            'Clean water supply',
            'Biosecurity measures'
        ],
        'prevention_ar': [
            'تحسين الظروف البيئية (تهوية، كثافة مناسبة)',
            'استخدام علف جيد النوعية',
            'برنامج تحصين ضد السالمونيلا',
            'تطهير دوري للحظائر والمعدات',
            'نظافة مناسبة',
            'مكافحة القوارض',
            'مصدر ماء نظيف',
            'إجراءات الأمن الحيوي'
        ]
    }
}

# EXACT COPY of your BroilerDiseaseClassifier from predict_broiler_fixed.py
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

# EXACT COPY of your BroilerDiseasePredictor from predict_broiler_fixed.py
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
        """Load the trained model with correct architecture - EXACT COPY"""
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
        """Predict disease from image - EXACT COPY"""
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

# Fecal Disease Predictor using EfficientNetB3
# Fecal Disease Predictor using EXACT same architecture as training
class ChickenDiseaseModel(nn.Module):
    def __init__(self, num_classes, dropout_rate=0.45):
        super(ChickenDiseaseModel, self).__init__()
        
        # Use EfficientNet as backbone - EXACT COPY from training
        self.backbone = models.efficientnet_b3(pretrained=False)
        
        # Replace classifier - EXACT COPY from training
        in_features = self.backbone.classifier[1].in_features
        self.backbone.classifier = nn.Identity()
        
        self.classifier = nn.Sequential(
            nn.BatchNorm1d(in_features),
            nn.Linear(in_features, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout_rate),
            nn.Linear(256, num_classes)
        )
        
        # Initialize weights
        self._initialize_weights()
    
    def _initialize_weights(self):
        for m in self.classifier.modules():
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0, 0.01)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
    
    def forward(self, x):
        features = self.backbone(x)
        output = self.classifier(features)
        return output

class FecalDiseasePredictor:
    def __init__(self, model_path="efficientnetb3-Chicken_Disease-95.66.pth"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"✅ Fecal Predictor Using device: {self.device}")
        
        self.model = self.load_model(model_path)
        self.transform = transforms.Compose([
            transforms.Resize((300, 300)),  # EfficientNet typically uses 300x300
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        
    def load_model(self, model_path):
        """Load the trained EfficientNetB3 model with EXACT architecture"""
        try:
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Fecal model file not found: {model_path}")
            
            # Load checkpoint
            checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)
            print(f"📁 Fecal Checkpoint keys: {list(checkpoint.keys())}")
            
            # Create model with EXACT same architecture as training
            model = ChickenDiseaseModel(num_classes=4, dropout_rate=0.45)  # 4 classes for fecal diseases
            
            # Load state dict
            if 'model_state_dict' in checkpoint:
                model.load_state_dict(checkpoint['model_state_dict'])
            else:
                model.load_state_dict(checkpoint)
            
            model.to(self.device)
            model.eval()
            
            print(f"✅ Fecal disease model loaded successfully!")
            print(f"📊 Fecal Classes: {FECAL_CLASSES}")
            print(f"🎯 Number of fecal classes: {len(FECAL_CLASSES)}")
            
            return model
            
        except Exception as e:
            print(f"❌ Error loading fecal disease model: {e}")
            import traceback
            traceback.print_exc()
            raise e
    
    def predict(self, image_path):
        """Predict fecal disease from image"""
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
                
            predicted_class = FECAL_CLASSES[predicted_idx.item()]
            confidence_score = confidence.item()
            
            # Get all class probabilities
            all_probs = {FECAL_CLASSES[i]: float(prob) 
                        for i, prob in enumerate(probabilities.cpu().numpy()[0])}
            
            return {
                'predicted_class': predicted_class,
                'confidence': confidence_score,
                'all_probabilities': all_probs,
                'status': 'success'
            }
            
        except Exception as e:
            print(f"❌ Fecal prediction error: {e}")
            return {
                'predicted_class': 'Error',
                'confidence': 0.0,
                'error': str(e),
                'status': 'error'
            }
    
    def predict(self, image_path):
        """Predict fecal disease from image"""
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
                
            predicted_class = FECAL_CLASSES[predicted_idx.item()]
            confidence_score = confidence.item()
            
            # Get all class probabilities
            all_probs = {FECAL_CLASSES[i]: float(prob) 
                        for i, prob in enumerate(probabilities.cpu().numpy()[0])}
            
            return {
                'predicted_class': predicted_class,
                'confidence': confidence_score,
                'all_probabilities': all_probs,
                'status': 'success'
            }
            
        except Exception as e:
            print(f"❌ Fecal prediction error: {e}")
            return {
                'predicted_class': 'Error',
                'confidence': 0.0,
                'error': str(e),
                'status': 'error'
            }

# Load disease predictors
try:
    disease_predictor = BroilerDiseasePredictor('best_broiler_model.pth')
    print("✅ Broiler disease predictor loaded successfully!")
except Exception as e:
    print(f"❌ Error loading broiler disease predictor: {e}")
    disease_predictor = None

try:
    fecal_predictor = FecalDiseasePredictor('efficientnetb3-Chicken_Disease-95.66.pth')
    print("✅ Fecal disease predictor loaded successfully!")
except Exception as e:
    print(f"❌ Error loading fecal disease predictor: {e}")
    fecal_predictor = None

# Routes for serving pages
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/disease')
def disease():
    return render_template('disease.html')

@app.route('/weight')
def weight():
    return render_template('weight.html')

# Weight Estimation Utility Functions
def filter_duplicate_detections(result, iou_threshold=0.5, conf_diff_threshold=0.2):
    """
    Filter duplicate detections by:
    1. Removing low-confidence duplicates that overlap with high-confidence ones
    2. Merging detections that are too close together
    """
    if result.boxes is None or len(result.boxes) == 0:
        return result
    
    boxes = result.boxes.xyxy.cpu()
    confidences = result.boxes.conf.cpu()
    classes = result.boxes.cls.cpu()
    
    # Sort by confidence (highest first)
    sorted_indices = torch.argsort(confidences, descending=True)
    keep = []
    suppressed = set()
    
    for i in sorted_indices:
        if i.item() in suppressed:
            continue
        
        keep.append(i.item())
        box_i = boxes[i]
        
        # Check overlap with remaining boxes
        for j in sorted_indices:
            if j.item() in suppressed or j.item() == i.item():
                continue
            
            box_j = boxes[j]
            
            # Calculate IoU
            x1_i, y1_i, x2_i, y2_i = box_i
            x1_j, y1_j, x2_j, y2_j = box_j
            
            # Intersection
            x1_inter = max(x1_i, x1_j)
            y1_inter = max(y1_i, y1_j)
            x2_inter = min(x2_i, x2_j)
            y2_inter = min(y2_i, y2_j)
            
            if x2_inter > x1_inter and y2_inter > y1_inter:
                inter_area = (x2_inter - x1_inter) * (y2_inter - y1_inter)
                box_i_area = (x2_i - x1_i) * (y2_i - y1_i)
                box_j_area = (x2_j - x1_j) * (y2_j - y1_j)
                union_area = box_i_area + box_j_area - inter_area
                
                if union_area > 0:
                    iou = inter_area / union_area
                    
                    # Suppress if high IoU and similar class, or if one is much less confident
                    if iou > iou_threshold:
                        conf_diff = abs(confidences[i] - confidences[j])
                        same_class = classes[i] == classes[j]
                        
                        # Suppress duplicate if:
                        # 1. High IoU and same class, OR
                        # 2. High IoU and one is much less confident
                        if (same_class and iou > 0.6) or (conf_diff > conf_diff_threshold and confidences[j] < confidences[i]):
                            suppressed.add(j.item())
    
    # Create filtered result
    if len(keep) < len(boxes):
        # Filter boxes, masks, etc.
        keep_tensor = torch.tensor(keep)
        result.boxes = result.boxes[keep_tensor]
        if result.masks is not None:
            result.masks = result.masks[keep_tensor]
    
    return result

def extract_weight_value(class_name):
    """Extract numeric weight value from class name and convert to kg"""
    try:
        # Clean up the class name to extract the numeric value
        weight_str = class_name.replace(' ', '').replace('-gm-', '').replace('-gm', '').replace('gm', '')
        # Convert to integer (removes any decimal part)
        weight_g = int(weight_str)
        # Convert grams to kilograms and return
        return weight_g / 1000.0
    except:
        return None

# API routes for model inference
@app.route('/analyze-image', methods=['POST'])
def analyze_image():
    if model is None:
        return jsonify({'error': 'Model not loaded'}), 500
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = f"{uuid.uuid4().hex}.jpg"
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    output_filename = f"{uuid.uuid4().hex}_annotated.jpg"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        image_file.save(input_path)
        results = model(input_path)[0]

        healthy_count, unhealthy_count = 0, 0
        for box in results.boxes:
            cls = int(box.cls[0])
            if cls == 0:
                healthy_count += 1
            else:
                unhealthy_count += 1

        # Create annotated image
        annotated = results.plot()
        cv2.imwrite(output_path, annotated)

        return jsonify({
            'success': True,
            'output_image': f"/outputs/{output_filename}",
            'healthy_count': healthy_count,
            'unhealthy_count': unhealthy_count,
            'total_count': healthy_count + unhealthy_count
        })
    except Exception as e:
        print(f"Error in analyze-image: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/analyze-video', methods=['POST'])
def analyze_video():
    if model is None:
        return jsonify({'error': 'Model not loaded'}), 500
    
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Use MP4 format for better browser compatibility
    original_filename = secure_filename(video_file.filename)
    file_ext = os.path.splitext(original_filename)[1].lower()
    input_filename = f"{uuid.uuid4().hex}{file_ext}"
    input_path = os.path.join(UPLOAD_FOLDER, input_filename)
    
    output_filename = f"{uuid.uuid4().hex}_annotated.mp4"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        video_file.save(input_path)

        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            return jsonify({'error': 'Could not open video file'}), 400

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Save video metadata
        with open(os.path.join(OUTPUT_FOLDER, "video_meta.json"), "w") as f:
            json.dump({"width": width, "height": height, "fps": fps}, f)

        if fps == 0 or np.isnan(fps):
            fps = 25.0

        # Use MP4V codec for MP4 format (browser compatible)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        print(f"Saving annotated video: {output_path}")
        print(f"Resolution: {width}x{height}, FPS: {fps}")

        # Statistics tracking
        frame_stats = []  # Store counts per frame
        track_health = {}  # {id: 'Healthy' / 'Unhealthy'}
        next_id = 0
        track_positions = {}

        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            results = model(frame)[0]
            current_detections = []
            frame_healthy = 0
            frame_unhealthy = 0

            for box in results.boxes:
                x1, y1, x2, y2 = map(float, box.xyxy[0])
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                label = 'Healthy' if cls == 0 else 'Unhealthy'
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                
                # Count for this frame
                if cls == 0:
                    frame_healthy += 1
                else:
                    frame_unhealthy += 1
                
                current_detections.append((cx, cy, x1, y1, x2, y2, label, conf))

            # Store frame statistics
            frame_stats.append({
                'healthy': frame_healthy,
                'unhealthy': frame_unhealthy,
                'total': frame_healthy + frame_unhealthy
            })

            # Simple tracking by proximity
            used_ids = set()
            for cx, cy, x1, y1, x2, y2, label, conf in current_detections:
                # Find closest existing track
                min_dist = float('inf')
                best_id = None
                
                for track_id, positions in track_positions.items():
                    if track_id in used_ids:
                        continue
                    if positions:
                        last_x, last_y = positions[-1]
                        dist = np.sqrt((cx - last_x)**2 + (cy - last_y)**2)
                        if dist < min_dist and dist < 50:  # Threshold for same chicken
                            min_dist = dist
                            best_id = track_id
                
                if best_id is not None:
                    track_id = best_id
                    used_ids.add(track_id)
                else:
                    track_id = next_id
                    next_id += 1
                    track_positions[track_id] = []

                # Update track
                track_positions[track_id].append((cx, cy))
                track_health[track_id] = label

                # Draw bounding box and label
                color = (0, 255, 0) if label == 'Healthy' else (0, 0, 255)
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                
                # Label with track ID
                label_text = f"{label} ID:{track_id}"
                cv2.putText(frame, label_text, (int(x1), int(y1)-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            out.write(frame)
            frame_count += 1
            
            # Print progress every 50 frames
            if frame_count % 50 == 0:
                print(f"Processed {frame_count} frames...")

        cap.release()
        out.release()

        print(f"Video processing completed. Total frames: {frame_count}")

        # Calculate overall statistics
        total_frames = len(frame_stats)
        if total_frames > 0:
            # Use the frame with maximum detection as representative
            max_frame = max(frame_stats, key=lambda x: x['total'])
            healthy_count = max_frame['healthy']
            unhealthy_count = max_frame['unhealthy']
            total_count = max_frame['total']
            
            # Alternative: Use average across frames
            avg_healthy = sum(f['healthy'] for f in frame_stats) // total_frames
            avg_unhealthy = sum(f['unhealthy'] for f in frame_stats) // total_frames
            avg_total = avg_healthy + avg_unhealthy
            
            print(f"Video analysis completed: {total_count} chickens (max frame), {avg_total} chickens (average)")
        else:
            healthy_count = 0
            unhealthy_count = 0
            total_count = 0
            print("No frames processed in video")

        # Save tracked positions for heatmap
        tracked_positions = []
        for track_id, coords in track_positions.items():
            for x, y in coords:
                tracked_positions.append((track_id, x, y))

        np.save(os.path.join(OUTPUT_FOLDER, "tracked_chickens.npy"), tracked_positions)

        return jsonify({
            'success': True,
            'annotated_video': output_filename,
            'healthy_count': healthy_count,
            'unhealthy_count': unhealthy_count,
            'total_count': total_count,
            'message': f'Video analysis completed: {total_count} chickens detected in {frame_count} frames',
            'frame_stats': {
                'total_frames': total_frames,
                'max_detection': total_count,
                'average_detection': avg_total if total_frames > 0 else 0
            }
        })

    except Exception as e:
        print(f"Error in analyze-video: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/analyze-broiler-disease', methods=['POST'])
def analyze_broiler_disease():
    if disease_predictor is None:
        # If predictor not loaded, use mock analysis
        return analyze_broiler_disease_mock()
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = f"{uuid.uuid4().hex}_disease.jpg"
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    output_filename = f"{uuid.uuid4().hex}_disease_annotated.jpg"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        # Save and process image
        image_file.save(input_path)
        
        # Use your EXACT working predictor
        result = disease_predictor.predict(input_path)
        
        if result['status'] != 'success':
            raise Exception(result.get('error', 'Prediction failed'))
        
        predicted_class = result['predicted_class']
        confidence_score = result['confidence']
        all_probabilities = result['all_probabilities']
        
        # Get disease information (handle different capitalization)
        disease_key = predicted_class.lower() if predicted_class.lower() in [k.lower() for k in DISEASE_INFO.keys()] else predicted_class
        if disease_key not in DISEASE_INFO:
            # Try exact match
            disease_key = predicted_class
        disease_data = DISEASE_INFO.get(disease_key, DISEASE_INFO.get('Healthy', {}))
        
        # Create annotated image
        original_image = Image.open(input_path).convert('RGB')
        annotated_image = original_image.copy()
        draw = ImageDraw.Draw(annotated_image)
        
        # Add prediction text to image
        try:
            # Try to use a larger font
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            except:
                font = ImageFont.load_default()
        
        # Choose color based on diagnosis
        if predicted_class.lower() == 'healthy':
            color = (0, 255, 0)  # Green for healthy
        else:
            color = (255, 0, 0)  # Red for diseases
        
        text = f"{disease_data.get('name', predicted_class)} ({confidence_score:.1%})"
        draw.text((10, 10), text, fill=color, font=font)
        
        # Add second line with top probabilities
        top_probs = sorted(all_probabilities.items(), key=lambda x: x[1], reverse=True)[:3]
        second_line = " | ".join([f"{k}:{v:.1%}" for k, v in top_probs])
        if len(second_line) > 50:  # Truncate if too long
            second_line = second_line[:47] + "..."
        draw.text((10, 40), second_line, fill=color, font=font)
        
        # Save annotated image
        annotated_image.save(output_path)
        
        # Return all disease information
        response_data = {
            'success': True,
            'diagnosis': disease_data.get('name', predicted_class),
            'diagnosis_ar': disease_data.get('name_ar', ''),
            'confidence': confidence_score,
            'description': disease_data.get('description', ''),
            'description_ar': disease_data.get('description_ar', ''),
            'symptoms': disease_data.get('symptoms', []),
            'symptoms_ar': disease_data.get('symptoms_ar', []),
            'treatment': disease_data.get('treatment', []),
            'treatment_ar': disease_data.get('treatment_ar', []),
            'prevention': disease_data.get('prevention', []),
            'prevention_ar': disease_data.get('prevention_ar', []),
            'annotated_image': f"/outputs/{output_filename}",
            'all_probabilities': all_probabilities,
            'message': f'Diagnosis: {disease_data.get("name", predicted_class)} with {confidence_score:.1%} confidence',
            'is_mock': False
        }
        
        # Add additional fields if they exist
        if 'causative_agent' in disease_data:
            response_data['causative_agent'] = disease_data['causative_agent']
            response_data['causative_agent_ar'] = disease_data.get('causative_agent_ar', '')
        if 'age_at_risk' in disease_data:
            response_data['age_at_risk'] = disease_data['age_at_risk']
            response_data['age_at_risk_ar'] = disease_data.get('age_at_risk_ar', '')
        if 'lesions' in disease_data:
            response_data['lesions'] = disease_data['lesions']
            response_data['lesions_ar'] = disease_data.get('lesions_ar', '')
        if 'infection_sources' in disease_data:
            response_data['infection_sources'] = disease_data['infection_sources']
            response_data['infection_sources_ar'] = disease_data.get('infection_sources_ar', [])
        if 'droppings' in disease_data:
            response_data['droppings'] = disease_data['droppings']
            response_data['droppings_ar'] = disease_data.get('droppings_ar', '')
        
        return jsonify(response_data)

    except Exception as e:
        print(f"Error in broiler disease analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        # Fallback to mock analysis
        return analyze_broiler_disease_mock()

@app.route('/analyze-fecal-disease', methods=['POST'])
def analyze_fecal_disease():
    if fecal_predictor is None:
        # If predictor not loaded, use mock analysis
        return analyze_fecal_disease_mock()
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = f"{uuid.uuid4().hex}_fecal.jpg"
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    output_filename = f"{uuid.uuid4().hex}_fecal_annotated.jpg"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        # Save and process image
        image_file.save(input_path)
        
        # Use fecal disease predictor
        result = fecal_predictor.predict(input_path)
        
        if result['status'] != 'success':
            raise Exception(result.get('error', 'Prediction failed'))
        
        predicted_class = result['predicted_class']
        confidence_score = result['confidence']
        all_probabilities = result['all_probabilities']
        
        # Get disease information
        disease_data = FECAL_INFO.get(predicted_class, FECAL_INFO.get('Healthy', {}))
        
        # Create annotated image
        original_image = Image.open(input_path).convert('RGB')
        annotated_image = original_image.copy()
        draw = ImageDraw.Draw(annotated_image)
        
        # Add prediction text to image
        try:
            # Try to use a larger font
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            except:
                font = ImageFont.load_default()
        
        # Choose color based on diagnosis
        if predicted_class.lower() == 'healthy':
            color = (0, 255, 0)  # Green for healthy
        else:
            color = (255, 0, 0)  # Red for diseases
        
        text = f"{disease_data.get('name', predicted_class)} ({confidence_score:.1%})"
        draw.text((10, 10), text, fill=color, font=font)
        
        # Add second line with top probabilities
        top_probs = sorted(all_probabilities.items(), key=lambda x: x[1], reverse=True)[:3]
        second_line = " | ".join([f"{k}:{v:.1%}" for k, v in top_probs])
        if len(second_line) > 50:  # Truncate if too long
            second_line = second_line[:47] + "..."
        draw.text((10, 40), second_line, fill=color, font=font)
        
        # Save annotated image
        annotated_image.save(output_path)
        
        # Return all disease information
        response_data = {
            'success': True,
            'diagnosis': disease_data.get('name', predicted_class),
            'diagnosis_ar': disease_data.get('name_ar', ''),
            'confidence': confidence_score,
            'description': disease_data.get('description', ''),
            'description_ar': disease_data.get('description_ar', ''),
            'symptoms': disease_data.get('symptoms', []),
            'symptoms_ar': disease_data.get('symptoms_ar', []),
            'treatment': disease_data.get('treatment', []),
            'treatment_ar': disease_data.get('treatment_ar', []),
            'prevention': disease_data.get('prevention', []),
            'prevention_ar': disease_data.get('prevention_ar', []),
            'annotated_image': f"/outputs/{output_filename}",
            'all_probabilities': all_probabilities,
            'message': f'Fecal Analysis: {disease_data.get("name", predicted_class)} with {confidence_score:.1%} confidence',
            'is_mock': False
        }
        
        # Add additional fields if they exist
        if 'causative_agent' in disease_data:
            response_data['causative_agent'] = disease_data['causative_agent']
            response_data['causative_agent_ar'] = disease_data.get('causative_agent_ar', '')
        if 'age_at_risk' in disease_data:
            response_data['age_at_risk'] = disease_data['age_at_risk']
            response_data['age_at_risk_ar'] = disease_data.get('age_at_risk_ar', '')
        if 'lesions' in disease_data:
            response_data['lesions'] = disease_data['lesions']
            response_data['lesions_ar'] = disease_data.get('lesions_ar', '')
        if 'infection_sources' in disease_data:
            response_data['infection_sources'] = disease_data['infection_sources']
            response_data['infection_sources_ar'] = disease_data.get('infection_sources_ar', [])
        if 'droppings' in disease_data:
            response_data['droppings'] = disease_data['droppings']
            response_data['droppings_ar'] = disease_data.get('droppings_ar', '')
        
        return jsonify(response_data)

    except Exception as e:
        print(f"Error in fecal disease analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        # Fallback to mock analysis
        return analyze_fecal_disease_mock()

def process_video_for_weight_estimation(video_path, output_path):
    """
    Process a video file to estimate weights of broilers in each frame.
    
    Args:
        video_path (str): Path to the input video file
        output_path (str): Path to save the processing results
        
    Returns:
        dict: Dictionary containing processing results including:
            - processed_frames: Number of frames processed
            - broilers: List of detected broilers with weights
            - average_weight: Average weight across all detections
            - weight_category: Weight category (Underweight, Optimal, Overweight)
    """
    if weight_model is None:
        raise ValueError("Weight estimation model not loaded")
    
    # Open video file
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")
    
    # Get video properties
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Store results
    all_broilers = []
    processed_frames = 0
    frame_number = 0
    
    # Process frames
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Skip frames to process at 1 FPS (adjust as needed)
        if frame_number % int(fps) != 0:
            frame_number += 1
            continue
            
        # Run inference
        results = weight_model(frame)[0]
        
        # Process detections
        if results.boxes is not None and len(results.boxes) > 0:
            for i, box in enumerate(results.boxes):
                # Get bounding box
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                
                # Skip low confidence detections
                if conf < 0.5:  # Adjust confidence threshold as needed
                    continue
                
                # Estimate weight (using the same logic as in the image processing)
                weight = None
                
                # Method 1: Check if weight is stored as a custom attribute
                if hasattr(box, 'weight'):
                    try:
                        weight_val = box.weight
                        if isinstance(weight_val, (list, tuple, np.ndarray)):
                            weight = float(weight_val[0])
                        else:
                            weight = float(weight_val)
                    except:
                        pass
                
                # Method 2: Estimate from bounding box area if weight not found
                if weight is None or weight <= 0:
                    box_area = (x2 - x1) * (y2 - y1)
                    img_area = frame.shape[0] * frame.shape[1]
                    area_ratio = box_area / img_area if img_area > 0 else 0
                    weight = 1.5 + (area_ratio * 2.0)  # Scale to 1.5-3.5 kg range
                    weight = max(1.0, min(4.0, weight))
                
                # Add broiler to results
                all_broilers.append({
                    'frame': frame_number,
                    'frame_time': f"{frame_number/fps:.1f}s",
                    'bbox': [x1, y1, x2, y2],
                    'weight': round(weight, 2),
                    'confidence': round(conf, 4)
                })
        
        processed_frames += 1
        frame_number += 1
        
        # Show progress
        if frame_number % 10 == 0:
            print(f"Processed {frame_number}/{frame_count} frames")
    
    # Release video capture
    cap.release()
    
    # Calculate statistics
    total_weight = sum(b['weight'] for b in all_broilers)
    avg_weight = total_weight / len(all_broilers) if all_broilers else 0
    
    # Determine weight category
    if avg_weight < 2.0:
        category = 'Underweight'
    elif 2.0 <= avg_weight <= 2.8:
        category = 'Optimal'
    else:
        category = 'Overweight'
    
    # Prepare results
    results = {
        'processed_frames': processed_frames,
        'total_frames': frame_count,
        'broilers': all_broilers,
        'average_weight': round(avg_weight, 2),
        'total_weight': round(total_weight, 2),
        'weight_category': category,
        'detection_count': len(all_broilers)
    }
    
    # Save results to JSON file
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    return results

@app.route('/estimate-weight-video', methods=['POST'])
def estimate_weight_video():
    """Estimate weight of broilers from video using YOLOv8 semantic segmentation model"""
    if weight_model is None:
        return jsonify({'error': 'Weight estimation model not loaded'}), 500
    
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Generate unique filenames
    video_filename = f"{uuid.uuid4().hex}_weight.mp4"
    output_filename = f"{uuid.uuid4().hex}_weight_results.json"
    input_path = os.path.join(UPLOAD_FOLDER, video_filename)
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        # Save video file
        video_file.save(input_path)
        
        # Process video
        results = process_video_for_weight_estimation(input_path, output_path)
        
        # Return results
        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Fallback routes for mock analysis
@app.route('/analyze-broiler-disease-mock', methods=['POST'])
def analyze_broiler_disease_mock():
    """Mock analysis for testing when model file is not available"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = f"{uuid.uuid4().hex}_disease.jpg"
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        image_file.save(input_path)
        image = Image.open(input_path).convert('RGB')
        
        # Consistent mock prediction based on image hash (so same image gives same result)
        import hashlib
        image_hash = hashlib.md5(image.tobytes()).hexdigest()
        hash_int = int(image_hash[:8], 16)
        predicted_index = hash_int % len(DISEASE_CLASSES)
        predicted_class = DISEASE_CLASSES[predicted_index]
        confidence_score = 0.85 + (hash_int % 100) / 500  # 0.85-0.95 range
        
        # Get disease information (handle different capitalization)
        disease_key = predicted_class.lower() if predicted_class.lower() in [k.lower() for k in DISEASE_INFO.keys()] else predicted_class
        if disease_key not in DISEASE_INFO:
            disease_key = predicted_class
        disease_data = DISEASE_INFO.get(disease_key, DISEASE_INFO.get('Healthy', {}))
        
        # Create simple annotated image
        output_filename = f"{uuid.uuid4().hex}_disease_annotated.jpg"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        annotated_image = image.copy()
        draw = ImageDraw.Draw(annotated_image)
        
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        # Choose color based on diagnosis
        if predicted_class.lower() == 'healthy':
            color = (0, 255, 0)  # Green for healthy
        else:
            color = (255, 0, 0)  # Red for diseases
        
        text = f"{disease_data.get('name', predicted_class)} ({confidence_score:.1%}) - MOCK"
        draw.text((10, 10), text, fill=color, font=font)
        annotated_image.save(output_path)
        
        # Return all disease information (same structure as real endpoint)
        response_data = {
            'success': True,
            'diagnosis': disease_data.get('name', predicted_class),
            'diagnosis_ar': disease_data.get('name_ar', ''),
            'confidence': confidence_score,
            'description': disease_data.get('description', ''),
            'description_ar': disease_data.get('description_ar', ''),
            'symptoms': disease_data.get('symptoms', []),
            'symptoms_ar': disease_data.get('symptoms_ar', []),
            'treatment': disease_data.get('treatment', []),
            'treatment_ar': disease_data.get('treatment_ar', []),
            'prevention': disease_data.get('prevention', []),
            'prevention_ar': disease_data.get('prevention_ar', []),
            'annotated_image': f"/outputs/{output_filename}",
            'message': f'MOCK Diagnosis: {disease_data.get("name", predicted_class)} with {confidence_score:.1%} confidence',
            'is_mock': True
        }
        
        # Add additional fields if they exist
        if 'causative_agent' in disease_data:
            response_data['causative_agent'] = disease_data['causative_agent']
            response_data['causative_agent_ar'] = disease_data.get('causative_agent_ar', '')
        if 'age_at_risk' in disease_data:
            response_data['age_at_risk'] = disease_data['age_at_risk']
            response_data['age_at_risk_ar'] = disease_data.get('age_at_risk_ar', '')
        if 'lesions' in disease_data:
            response_data['lesions'] = disease_data['lesions']
            response_data['lesions_ar'] = disease_data.get('lesions_ar', '')
        if 'infection_sources' in disease_data:
            response_data['infection_sources'] = disease_data['infection_sources']
            response_data['infection_sources_ar'] = disease_data.get('infection_sources_ar', [])
        if 'droppings' in disease_data:
            response_data['droppings'] = disease_data['droppings']
            response_data['droppings_ar'] = disease_data.get('droppings_ar', '')
        
        return jsonify(response_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analyze-fecal-disease-mock', methods=['POST'])
def analyze_fecal_disease_mock():
    """Mock analysis for fecal disease when model file is not available"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = f"{uuid.uuid4().hex}_fecal.jpg"
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        image_file.save(input_path)
        image = Image.open(input_path).convert('RGB')
        
        # Consistent mock prediction based on image hash (so same image gives same result)
        import hashlib
        image_hash = hashlib.md5(image.tobytes()).hexdigest()
        hash_int = int(image_hash[:8], 16)
        predicted_index = hash_int % len(FECAL_CLASSES)
        predicted_class = FECAL_CLASSES[predicted_index]
        confidence_score = 0.85 + (hash_int % 100) / 500  # 0.85-0.95 range
        
        # Get disease information
        disease_data = FECAL_INFO.get(predicted_class, FECAL_INFO.get('Healthy', {}))
        
        # Create simple annotated image
        output_filename = f"{uuid.uuid4().hex}_fecal_annotated.jpg"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        annotated_image = image.copy()
        draw = ImageDraw.Draw(annotated_image)
        
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        # Choose color based on diagnosis
        if predicted_class.lower() == 'healthy':
            color = (0, 255, 0)  # Green for healthy
        else:
            color = (255, 0, 0)  # Red for diseases
        
        text = f"{disease_data.get('name', predicted_class)} ({confidence_score:.1%}) - MOCK"
        draw.text((10, 10), text, fill=color, font=font)
        annotated_image.save(output_path)
        
        # Return all disease information (same structure as real endpoint)
        response_data = {
            'success': True,
            'diagnosis': disease_data.get('name', predicted_class),
            'diagnosis_ar': disease_data.get('name_ar', ''),
            'confidence': confidence_score,
            'description': disease_data.get('description', ''),
            'description_ar': disease_data.get('description_ar', ''),
            'symptoms': disease_data.get('symptoms', []),
            'symptoms_ar': disease_data.get('symptoms_ar', []),
            'treatment': disease_data.get('treatment', []),
            'treatment_ar': disease_data.get('treatment_ar', []),
            'prevention': disease_data.get('prevention', []),
            'prevention_ar': disease_data.get('prevention_ar', []),
            'annotated_image': f"/outputs/{output_filename}",
            'message': f'MOCK Fecal Analysis: {disease_data.get("name", predicted_class)} with {confidence_score:.1%} confidence',
            'is_mock': True
        }
        
        # Add additional fields if they exist
        if 'causative_agent' in disease_data:
            response_data['causative_agent'] = disease_data['causative_agent']
            response_data['causative_agent_ar'] = disease_data.get('causative_agent_ar', '')
        if 'age_at_risk' in disease_data:
            response_data['age_at_risk'] = disease_data['age_at_risk']
            response_data['age_at_risk_ar'] = disease_data.get('age_at_risk_ar', '')
        if 'lesions' in disease_data:
            response_data['lesions'] = disease_data['lesions']
            response_data['lesions_ar'] = disease_data.get('lesions_ar', '')
        if 'infection_sources' in disease_data:
            response_data['infection_sources'] = disease_data['infection_sources']
            response_data['infection_sources_ar'] = disease_data.get('infection_sources_ar', [])
        if 'droppings' in disease_data:
            response_data['droppings'] = disease_data['droppings']
            response_data['droppings_ar'] = disease_data.get('droppings_ar', '')
        
        return jsonify(response_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/estimate-weight', methods=['POST'])
def estimate_weight():
    """Estimate weight of broilers from image using YOLOv8 semantic segmentation model"""
    if weight_model is None:
        return jsonify({'error': 'Weight estimation model not loaded'}), 500
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
    
    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = f"{uuid.uuid4().hex}_weight.jpg"
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    output_filename = f"{uuid.uuid4().hex}_weight_annotated.jpg"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        # Save uploaded image
        image_file.save(input_path)
        
        # Load image for processing
        img = cv2.imread(input_path)
        if img is None:
            return jsonify({'error': 'Could not read image file'}), 400
        
        # Run inference with weight model
        results = weight_model(img)[0]
        
        # Filter duplicate detections
        results = filter_duplicate_detections(results)
        
        # Process results
        annotated_img = img.copy()
        detected_broilers = []
        total_weight = 0.0
        
        # Get class names if available
        class_names = getattr(weight_model, 'names', [])
        
        # Process detections
        if results.boxes is not None and len(results.boxes) > 0:
            for i, box in enumerate(results.boxes):
                # Get bounding box coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                cls_id = int(box.cls[0]) if hasattr(box, 'cls') else 0
                
                # Get class name if available
                class_name = class_names[cls_id] if cls_id < len(class_names) else f"class_{cls_id}"
                
                # Extract weight from class name if possible
                weight = extract_weight_value(class_name)
                
                # If weight not found in class name, try to get from mask if available
                if weight is None and results.masks is not None and i < len(results.masks.data):
                    try:
                        # Get mask for this detection
                        mask = results.masks.data[i]
                        if hasattr(mask, 'cpu'):
                            mask = mask.cpu().numpy()
                        elif hasattr(mask, 'numpy'):
                            mask = mask.numpy()
                        
                        # Calculate mask area
                        mask_area = np.sum(mask > 0.5)  # Count pixels in mask
                        img_area = img.shape[0] * img.shape[1]
                        area_ratio = mask_area / img_area if img_area > 0 else 0
                        
                        # Estimate weight from mask area (more accurate than bbox)
                        # Adjust these coefficients based on your training data
                        # Convert from grams to kilograms by dividing by 1000
                        weight_g = 1500 + (area_ratio * 2000)  # Scale to 1500-3500g range
                        weight_g = max(1000, min(4000, weight_g))  # Clamp to 1000-4000g
                        weight = weight_g / 1000.0  # Convert to kg
                    except Exception as e:
                        print(f"Could not extract weight from mask: {e}")
                        pass
                
                # Fallback: Estimate weight from bounding box area if still None
                if weight is None or weight <= 0:
                    # Estimate weight based on bounding box area
                    box_area = (x2 - x1) * (y2 - y1)
                    img_area = img.shape[0] * img.shape[1]
                    area_ratio = box_area / img_area if img_area > 0 else 0
                    
                    # Heuristic: larger area = heavier chicken
                    # Convert from grams to kilograms by dividing by 1000
                    weight_g = 1500 + (area_ratio * 2000)  # Scale to 1500-3500g range
                    weight_g = max(1000, min(4000, weight_g))  # Clamp to 1000-4000g
                    weight = weight_g / 1000.0  # Convert to kg
                
                # Draw bounding box
                color = (0, 255, 0)  # Green color for boxes
                thickness = 2
                cv2.rectangle(annotated_img, (x1, y1), (x2, y2), color, thickness)
                
                # Convert weight to grams and round to nearest gram
                weight_g = round(weight * 1000)
                
                # Draw weight label in grams
                label_text = f"{weight_g}g"
                label_size, _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                label_y = max(y1, label_size[1] + 10)
                
                # Draw label background
                cv2.rectangle(annotated_img, 
                            (x1, label_y - label_size[1] - 5), 
                            (x1 + label_size[0] + 5, label_y + 5), 
                            color, -1)
                
                # Draw label text
                cv2.putText(annotated_img, label_text, 
                          (x1 + 2, label_y), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
                
                detected_broilers.append({
                    'id': i + 1,
                    'weight': weight_g,  # Store in grams
                    'weight_kg': weight,  # Keep kg for backward compatibility
                    'confidence': round(conf, 2),
                    'bbox': [x1, y1, x2, y2]
                })
                total_weight += weight
        
        # Process segmentation masks if available (for semantic segmentation)
        # Note: Masks are already processed above for weight estimation
        # Here we just overlay them visually if they exist
        if results.masks is not None and len(results.masks.data) > 0:
            try:
                masks = results.masks.data
                if hasattr(masks, 'cpu'):
                    masks = masks.cpu().numpy()
                elif hasattr(masks, 'numpy'):
                    masks = masks.numpy()
                
                for i, mask in enumerate(masks):
                    if i >= len(detected_broilers):
                        break
                    
                    # Resize mask to image dimensions
                    mask_resized = cv2.resize(mask, (annotated_img.shape[1], annotated_img.shape[0]))
                    mask_uint8 = (mask_resized * 255).astype(np.uint8)
                    
                    # Create colored mask overlay (semi-transparent green)
                    colored_mask = np.zeros_like(annotated_img)
                    colored_mask[mask_uint8 > 128] = [0, 255, 0]  # Green overlay
                    
                    # Blend mask with image (30% opacity)
                    annotated_img = cv2.addWeighted(annotated_img, 0.7, colored_mask, 0.3, 0)
            except Exception as e:
                print(f"Could not overlay segmentation masks: {e}")
                pass
        
        # Save annotated image
        cv2.imwrite(output_path, annotated_img)
        
        # Calculate average weight in grams
        avg_weight_kg = total_weight / len(detected_broilers) if len(detected_broilers) > 0 else 0.0
        avg_weight_g = round(avg_weight_kg * 1000)
        total_weight_g = round(total_weight * 1000)
        
        # Determine weight category (still using kg for consistency)
        if avg_weight_kg < 2.0:
            category = 'Underweight'
        elif avg_weight_kg >= 2.0 and avg_weight_kg <= 2.8:
            category = 'Optimal'
        else:
            category = 'Overweight'
        
        return jsonify({
            'success': True,
            'annotated_image': f"/outputs/{output_filename}",
            'detected_count': len(detected_broilers),
            'broilers': detected_broilers,
            'total_weight': total_weight_g,  # in grams
            'total_weight_kg': round(total_weight, 2),  # keep kg for backward compatibility
            'average_weight': avg_weight_g,  # in grams
            'average_weight_kg': round(avg_weight_kg, 2),  # keep kg for backward compatibility
            'weight_category': category,
            'message': f'Detected {len(detected_broilers)} broiler(s) with average weight of {avg_weight_g}g'
        })
        
    except Exception as e:
        print(f"Error in weight estimation: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/generate-heatmap', methods=['GET'])
def generate_heatmap():
    try:
        tracked = np.load(os.path.join(OUTPUT_FOLDER, "tracked_chickens.npy"), allow_pickle=True)
        if len(tracked) == 0:
            return jsonify({'error': 'No tracked chicken positions available'}), 400

        # Load resolution
        with open(os.path.join(OUTPUT_FOLDER, "video_meta.json")) as f:
            meta = json.load(f)
        width = meta["width"]
        height = meta["height"]

        heatmap = np.zeros((int(height), int(width)), dtype=np.float32)

        # Grid to store unique IDs at each position
        grid = [[set() for _ in range(int(width))] for _ in range(int(height))]

        for tid, x, y in tracked:
            x = int(x)
            y = int(y)
            if 0 <= x < int(width) and 0 <= y < int(height):
                grid[y][x].add(tid)

        for y in range(int(height)):
            for x in range(int(width)):
                heatmap[y, x] = len(grid[y][x])

        heatmap_blurred = gaussian_filter(heatmap, sigma=25)
        normalized = cv2.normalize(heatmap_blurred, None, 0, 255, cv2.NORM_MINMAX)
        heatmap_colored = cv2.applyColorMap(normalized.astype(np.uint8), cv2.COLORMAP_JET)

        heatmap_filename = f"{uuid.uuid4().hex}_heatmap.jpg"
        heatmap_path = os.path.join(OUTPUT_FOLDER, heatmap_filename)
        cv2.imwrite(heatmap_path, heatmap_colored)

        return jsonify({
            'success': True,
            'heatmap_path': f"/outputs/{heatmap_filename}"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Serve output files
@app.route('/outputs/<filename>')
def serve_output_image(filename):
    filepath = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(filepath):
        return "File not found", 404
    
    # Set proper MIME type
    mime_type = 'image/jpeg' if filename.lower().endswith(('.jpg', '.jpeg')) else 'image/png'
    return send_file(filepath, mimetype=mime_type)

@app.route('/videooutputs/<path:filename>')
def serve_output_file(filename):
    filepath = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(filepath):
        return "File not found", 404
    
    # Set proper MIME type for MP4
    if filename.lower().endswith('.mp4'):
        mime_type = 'video/mp4'
    elif filename.lower().endswith('.avi'):
        mime_type = 'video/x-msvideo'
    else:
        mime_type = 'video/mp4'  # default
    
    print(f"Serving video file: {filepath}")
    return send_file(filepath, mimetype=mime_type)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)