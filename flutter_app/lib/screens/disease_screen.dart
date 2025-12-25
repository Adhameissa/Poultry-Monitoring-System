import 'dart:io' if (dart.library.html) 'dart:html' as io;
import 'package:poultry_monitoring/utils/html_stub.dart' if (dart.library.html) 'dart:html' as html;
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:image_picker/image_picker.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:font_awesome_flutter/font_awesome_flutter.dart';
import 'package:share_plus/share_plus.dart';
import 'package:path_provider/path_provider.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';
import '../models/disease_model.dart';

class DiseaseScreen extends StatefulWidget {
  const DiseaseScreen({super.key});

  @override
  State<DiseaseScreen> createState() => _DiseaseScreenState();
}

class _DiseaseScreenState extends State<DiseaseScreen> {
  final ApiService _apiService = ApiService();
  dynamic _broilerFile; // XFile on web, File on mobile
  dynamic _fecalFile; // XFile on web, File on mobile
  bool _isLoadingBroiler = false;
  bool _isLoadingFecal = false;
  DiseaseResponse? _broilerResults;
  DiseaseResponse? _fecalResults;

  // Helper function to write file and share on mobile (avoids File constructor issues)
  // Uses dynamic cast to avoid compiler checking dart:html.File constructor
  Future<void> _writeFileAndShare(String filePath, String content, BuildContext context) async {
    if (kIsWeb) {
      throw UnsupportedError('File writing not supported on web');
    }
    // Cast io.File to dynamic to avoid compiler checking constructor signature
    // On mobile, io.File is dart:io.File (1 arg), on web it's dart:html.File (2 args)
    // Use Function.apply to call constructor dynamically, avoiding static type checking
    final FileClass = io.File as dynamic;
    final file = Function.apply(FileClass, [filePath]);
    await file.writeAsString(content);
    
    await Share.shareXFiles(
      [XFile(file.path)],
      text: 'Disease Detection Report',
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Disease Detection'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Broiler Disease Detection Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 60,
                          height: 60,
                          decoration: const BoxDecoration(
                            color: AppTheme.primaryGreen,
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            FontAwesomeIcons.virus,
                            color: AppTheme.white,
                            size: 30,
                          ),
                        ),
                        const SizedBox(width: 15),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Broiler Disease Detection',
                                style: TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.darkGreen,
                                ),
                              ),
                              Text(
                                'Upload an image of a broiler chicken',
                                style: TextStyle(color: AppTheme.textColor),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    _buildUploadArea(
                      onTap: () => _pickBroilerImage(),
                      label: 'Click to upload broiler chicken image',
                      icon: FontAwesomeIcons.cloudUploadAlt,
                    ),
                    if (_broilerFile != null) ...[
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: AppTheme.lightGray,
                          borderRadius: BorderRadius.circular(5),
                          border: Border.all(color: AppTheme.primaryGreen),
                        ),
                        child: Text(
                          'Selected: ${kIsWeb ? (_broilerFile is XFile ? _broilerFile.name : 'file') : _broilerFile.path.split('/').last}',
                          style: const TextStyle(
                            color: AppTheme.darkGreen,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 15),
                    ElevatedButton(
                      onPressed: _broilerFile == null || _isLoadingBroiler
                          ? null
                          : _analyzeBroiler,
                      child: _isLoadingBroiler
                          ? const Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    valueColor: AlwaysStoppedAnimation<Color>(
                                      AppTheme.white,
                                    ),
                                  ),
                                ),
                                SizedBox(width: 10),
                                Text('Analyzing...'),
                              ],
                            )
                          : const Text('Analyze'),
                    ),
                  ],
                ),
              ),
            ),
            // Broiler Results
            if (_broilerResults != null) ...[
              const SizedBox(height: 20),
              _buildDiseaseResults(
                title: 'Broiler Disease Detection Results',
                results: _broilerResults!,
                onDownload: () => _downloadReport('broiler', _broilerResults!),
              ),
            ],
            const SizedBox(height: 30),
            // Fecal Analysis Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 60,
                          height: 60,
                          decoration: const BoxDecoration(
                            color: AppTheme.brown,
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            FontAwesomeIcons.poop,
                            color: AppTheme.white,
                            size: 30,
                          ),
                        ),
                        const SizedBox(width: 15),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Fecal Analysis',
                                style: TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.darkGreen,
                                ),
                              ),
                              Text(
                                'Upload a fecal image to detect diseases',
                                style: TextStyle(color: AppTheme.textColor),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    _buildUploadArea(
                      onTap: () => _pickFecalImage(),
                      label: 'Click to upload fecal image',
                      icon: FontAwesomeIcons.cloudUploadAlt,
                    ),
                    if (_fecalFile != null) ...[
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: AppTheme.lightGray,
                          borderRadius: BorderRadius.circular(5),
                          border: Border.all(color: AppTheme.primaryGreen),
                        ),
                        child: Text(
                          'Selected: ${kIsWeb ? (_fecalFile is XFile ? _fecalFile.name : 'file') : _fecalFile.path.split('/').last}',
                          style: const TextStyle(
                            color: AppTheme.darkGreen,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 15),
                    ElevatedButton(
                      onPressed: _fecalFile == null || _isLoadingFecal
                          ? null
                          : _analyzeFecal,
                      child: _isLoadingFecal
                          ? const Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    valueColor: AlwaysStoppedAnimation<Color>(
                                      AppTheme.white,
                                    ),
                                  ),
                                ),
                                SizedBox(width: 10),
                                Text('Analyzing...'),
                              ],
                            )
                          : const Text('Analyze'),
                    ),
                  ],
                ),
              ),
            ),
            // Fecal Results
            if (_fecalResults != null) ...[
              const SizedBox(height: 20),
              _buildDiseaseResults(
                title: 'Fecal Analysis Results',
                results: _fecalResults!,
                onDownload: () => _downloadReport('fecal', _fecalResults!),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildUploadArea({
    required VoidCallback onTap,
    required String label,
    required IconData icon,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.all(30),
        decoration: BoxDecoration(
          border: Border.all(color: AppTheme.lightGreen, width: 2, style: BorderStyle.solid),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          children: [
            Icon(icon, size: 40, color: AppTheme.lightGreen),
            const SizedBox(height: 15),
            Text(
              label,
              style: const TextStyle(
                color: AppTheme.textColor,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDiseaseResults({
    required String title,
    required DiseaseResponse results,
    required VoidCallback onDownload,
  }) {
    final disease = results.diseaseInfo;
    final confidencePercent = (results.confidence * 100).round();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.darkGreen,
                  ),
                ),
                ElevatedButton.icon(
                  onPressed: onDownload,
                  icon: const Icon(Icons.download, size: 18),
                  label: const Text('Download Report'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryGreen,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            // Image Preview
            if (results.annotatedImage != null)
              Card(
                child: CachedNetworkImage(
                  imageUrl: _apiService.getImageUrl(results.annotatedImage),
                  placeholder: (context, url) => const Center(
                    child: CircularProgressIndicator(),
                  ),
                  errorWidget: (context, url, error) => const Icon(Icons.error),
                ),
              ),
            const SizedBox(height: 20),
            // Diagnosis Header
            Container(
              padding: const EdgeInsets.all(15),
              decoration: BoxDecoration(
                color: AppTheme.lightGray,
                borderRadius: BorderRadius.circular(8),
                border: Border(left: BorderSide(color: AppTheme.primaryGreen, width: 4)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          disease.name,
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.darkGreen,
                          ),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [AppTheme.primaryGreen, AppTheme.darkGreen],
                          ),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Text(
                          '$confidencePercent%',
                          style: const TextStyle(
                            color: AppTheme.white,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ),
                  if (disease.nameAr.isNotEmpty) ...[
                    const SizedBox(height: 5),
                    Text(
                      disease.nameAr,
                      style: const TextStyle(
                        color: AppTheme.textColor,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 15),
            // Description
            Container(
              padding: const EdgeInsets.all(15),
              decoration: BoxDecoration(
                color: const Color(0xFFF0F8F0),
                borderRadius: BorderRadius.circular(8),
                border: Border(left: BorderSide(color: AppTheme.primaryGreen, width: 4)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    disease.description,
                    style: const TextStyle(color: AppTheme.textColor),
                  ),
                  if (disease.descriptionAr.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(
                      disease.descriptionAr,
                      style: const TextStyle(
                        color: AppTheme.textColor,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 15),
            // Confidence Bar
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Confidence: $confidencePercent%',
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    color: AppTheme.darkGreen,
                  ),
                ),
                const SizedBox(height: 5),
                ClipRRect(
                  borderRadius: BorderRadius.circular(7),
                  child: LinearProgressIndicator(
                    value: results.confidence,
                    minHeight: 14,
                    backgroundColor: Colors.grey[300],
                    valueColor: const AlwaysStoppedAnimation<Color>(AppTheme.primaryGreen),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            // Symptoms
            _buildInfoSection(
              icon: FontAwesomeIcons.exclamationTriangle,
              title: 'Symptoms',
              items: disease.symptoms,
              itemsAr: disease.symptomsAr,
            ),
            const SizedBox(height: 20),
            // Treatment
            _buildTreatmentSection(disease),
            const SizedBox(height: 20),
            // Prevention
            if (disease.prevention != null && disease.prevention!.isNotEmpty)
              _buildInfoSection(
                icon: FontAwesomeIcons.shieldAlt,
                title: 'Prevention Measures',
                items: disease.prevention!,
                itemsAr: disease.preventionAr,
              ),
            const SizedBox(height: 20),
            // Additional Info
            if (disease.causativeAgent != null ||
                disease.ageAtRisk != null ||
                disease.lesions != null)
              _buildAdditionalInfo(disease),
            const SizedBox(height: 20),
            // Medication Guidelines
            _buildMedicationGuidelines(),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoSection({
    required IconData icon,
    required String title,
    required List<String> items,
    List<String>? itemsAr,
  }) {
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: AppTheme.white,
        borderRadius: BorderRadius.circular(8),
        border: Border(left: BorderSide(color: AppTheme.primaryGreen, width: 4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: AppTheme.primaryGreen, size: 20),
              const SizedBox(width: 10),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.darkGreen,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ...items.asMap().entries.map((entry) {
            final index = entry.key;
            final item = entry.value;
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.circle, size: 8, color: AppTheme.primaryGreen),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item,
                          style: const TextStyle(color: AppTheme.textColor),
                        ),
                        if (itemsAr != null &&
                            index < itemsAr.length &&
                            itemsAr[index].isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Text(
                            itemsAr[index],
                            style: const TextStyle(
                              color: AppTheme.textColor,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildTreatmentSection(DiseaseInfo disease) {
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: AppTheme.white,
        borderRadius: BorderRadius.circular(8),
        border: Border(left: BorderSide(color: AppTheme.primaryGreen, width: 4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(FontAwesomeIcons.pills, color: AppTheme.primaryGreen, size: 20),
              SizedBox(width: 10),
              Text(
                'Recommended Treatment',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.darkGreen,
                ),
              ),
            ],
          ),
          const SizedBox(height: 15),
          ...disease.treatment.asMap().entries.map((entry) {
            final index = entry.key;
            final treatment = entry.value;
            
            if (treatment is Map) {
              // Detailed treatment object
              final arTreatment = index < disease.treatmentAr.length
                  ? disease.treatmentAr[index]
                  : null;
              
              return Container(
                margin: const EdgeInsets.only(bottom: 15),
                padding: const EdgeInsets.all(15),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [AppTheme.lightGray, AppTheme.white],
                  ),
                  borderRadius: BorderRadius.circular(8),
                  border: Border(left: BorderSide(color: AppTheme.primaryGreen, width: 3)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      treatment['name'] ?? 'Treatment',
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        color: AppTheme.darkGreen,
                        fontSize: 16,
                      ),
                    ),
                    if (treatment['dose'] != null) ...[
                      const SizedBox(height: 5),
                      Text('Dose: ${treatment['dose']}'),
                    ],
                    if (treatment['method'] != null) ...[
                      const SizedBox(height: 5),
                      Text('Method: ${treatment['method']}'),
                    ],
                    if (treatment['duration'] != null) ...[
                      const SizedBox(height: 5),
                      Text('Duration: ${treatment['duration']}'),
                    ],
                    if (treatment['description'] != null) ...[
                      const SizedBox(height: 5),
                      Text(treatment['description']),
                    ],
                    if (arTreatment != null && arTreatment is Map) ...[
                      const SizedBox(height: 8),
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppTheme.lightGray,
                          borderRadius: BorderRadius.circular(5),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (arTreatment['name'] != null)
                              Text(
                                arTreatment['name'],
                                style: const TextStyle(fontWeight: FontWeight.bold),
                              ),
                            if (arTreatment['dose'] != null)
                              Text('الجرعة: ${arTreatment['dose']}'),
                            if (arTreatment['method'] != null)
                              Text('طريقة: ${arTreatment['method']}'),
                            if (arTreatment['duration'] != null)
                              Text('المدة: ${arTreatment['duration']}'),
                            if (arTreatment['description'] != null)
                              Text(arTreatment['description']),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              );
            } else {
              // Simple string treatment
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.medical_services, size: 16, color: AppTheme.primaryGreen),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            treatment.toString(),
                            style: const TextStyle(color: AppTheme.textColor),
                          ),
                          if (disease.treatmentAr != null &&
                              index < disease.treatmentAr.length &&
                              disease.treatmentAr[index].toString().isNotEmpty) ...[
                            const SizedBox(height: 2),
                            Text(
                              disease.treatmentAr[index].toString(),
                              style: const TextStyle(
                                color: AppTheme.textColor,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              );
            }
          }),
        ],
      ),
    );
  }

  Widget _buildAdditionalInfo(DiseaseInfo disease) {
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF9E6),
        borderRadius: BorderRadius.circular(8),
        border: Border(left: BorderSide(color: AppTheme.yellow, width: 4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.info, color: AppTheme.yellow, size: 20),
              SizedBox(width: 10),
              Text(
                'Additional Information',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.darkGreen,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          if (disease.causativeAgent != null) ...[
            _buildInfoRow('Causative Agent', disease.causativeAgent!,
                disease.causativeAgentAr),
          ],
          if (disease.ageAtRisk != null) ...[
            _buildInfoRow('Age at Risk', disease.ageAtRisk!, disease.ageAtRiskAr),
          ],
          if (disease.lesions != null) ...[
            _buildInfoRow('Lesions', disease.lesions!, disease.lesionsAr),
          ],
          if (disease.infectionSources != null) ...[
            const SizedBox(height: 10),
            const Text(
              'Infection Sources:',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            ...disease.infectionSources!.map((source) => Padding(
                  padding: const EdgeInsets.only(left: 15, top: 5),
                  child: Text('• $source'),
                )),
          ],
          if (disease.droppings != null) ...[
            _buildInfoRow('Droppings', disease.droppings!, disease.droppingsAr),
          ],
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value, String? valueAr) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$label: $value',
            style: const TextStyle(color: AppTheme.textColor),
          ),
          if (valueAr != null && valueAr.isNotEmpty) ...[
            const SizedBox(height: 2),
            Text(
              valueAr,
              style: const TextStyle(
                color: AppTheme.textColor,
                fontSize: 12,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMedicationGuidelines() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFF0F8F0), AppTheme.white],
        ),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.primaryGreen, width: 2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(FontAwesomeIcons.clipboardList, color: AppTheme.primaryGreen),
              SizedBox(width: 10),
              Text(
                'ملخص عام للجرعات والإدارة',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.darkGreen,
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          _buildGuidelineSection(
            'قواعد عامة لإعطاء الأدوية:',
            [
              'حساب الجرعة: بناءً على وزن الطيور أو كمية الماء المتوقع استهلاكها',
              'وقت الإعطاء: في الصباح الباكر مع الماء النظيف',
              'فترة العلاج: 3-7 أيام حسب شدة المرض',
              'فترة السحب: مراعاة فترة سحب الأدوية قبل الذبح',
            ],
          ),
          const SizedBox(height: 15),
          _buildGuidelineSection(
            'بروتوكول الطوارئ:',
            [
              'التشخيص المبكر: مراقبة الأعراض اليومية',
              'العزل الفوري: فصل الطيور المريضة',
              'العلاج الجماعي: إعطاء العلاج للقطيع كاملاً في الأمراض المعدية',
              'التطهير: تنظيف وتطهير الحظيرة والمعدات',
            ],
          ),
          const SizedBox(height: 15),
          _buildGuidelineSection(
            'الوقاية خير من العلاج:',
            [
              '✅ برنامج تحصين منتظم',
              '✅ نظافة وتطهير دوري',
              '✅ تهوية جيدة وكثافة مناسبة',
              '✅ تغذية متوازنة وماء نظيف',
              '✅ إدارة الإجهاد وتجنب العوامل المسببة له',
            ],
            isPrevention: true,
          ),
          const SizedBox(height: 15),
          Container(
            padding: const EdgeInsets.all(15),
            decoration: BoxDecoration(
              color: const Color(0xFFFFF3E0),
              borderRadius: BorderRadius.circular(8),
              border: Border(left: BorderSide(color: Colors.red, width: 4)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.warning, color: Colors.red),
                    SizedBox(width: 10),
                    Text(
                      '🚨 تحذيرات مهمة:',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: Colors.red,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                _buildWarningItem('استشارة البيطري: ضرورية قبل بدء أي برنامج علاجي'),
                _buildWarningItem('الالتزام بالجرعات: تجنب زيادة الجرعات دون استشارة'),
                _buildWarningItem('فترات السحب: ضرورية لمنع بقايا الأدوية في اللحم والبيض'),
                _buildWarningItem('تسجيل العلاج: توثيق جميع العلاجات المستخدمة'),
                _buildWarningItem('مراقبة الاستجابة: تقييم فعالية العلاج بعد 48-72 ساعة'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildGuidelineSection(String title, List<String> items, {bool isPrevention = false}) {
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: AppTheme.white,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: AppTheme.darkGreen,
            ),
            textDirection: TextDirection.rtl,
            textAlign: TextAlign.right,
          ),
          const SizedBox(height: 10),
          ...items.map((item) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (isPrevention)
                      const Icon(Icons.check_circle, color: AppTheme.primaryGreen, size: 16)
                    else
                      const Icon(Icons.circle, size: 8, color: AppTheme.primaryGreen),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        item,
                        style: const TextStyle(color: AppTheme.textColor),
                        textDirection: TextDirection.rtl,
                        textAlign: TextAlign.right,
                      ),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildWarningItem(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.circle, size: 8, color: Colors.red),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: Colors.red),
              textDirection: TextDirection.rtl,
              textAlign: TextAlign.right,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _pickBroilerImage() async {
    final ImagePicker picker = ImagePicker();
    final XFile? image = await picker.pickImage(source: ImageSource.gallery);
    if (image != null) {
      setState(() {
        // Use XFile on both platforms - it works everywhere
        _broilerFile = image;
        _broilerResults = null;
      });
    }
  }

  Future<void> _pickFecalImage() async {
    final ImagePicker picker = ImagePicker();
    final XFile? image = await picker.pickImage(source: ImageSource.gallery);
    if (image != null) {
      setState(() {
        // Use XFile on both platforms - it works everywhere
        _fecalFile = image;
        _fecalResults = null;
      });
    }
  }

  Future<void> _analyzeBroiler() async {
    if (_broilerFile == null) return;

    setState(() {
      _isLoadingBroiler = true;
    });

    try {
      final response = await _apiService.analyzeBroilerDisease(_broilerFile!);
      setState(() {
        _broilerResults = response;
        _isLoadingBroiler = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Broiler disease analysis completed!'),
            backgroundColor: AppTheme.primaryGreen,
          ),
        );
      }
    } catch (e) {
      setState(() {
        _isLoadingBroiler = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Analysis failed: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _analyzeFecal() async {
    if (_fecalFile == null) return;

    setState(() {
      _isLoadingFecal = true;
    });

    try {
      final response = await _apiService.analyzeFecalDisease(_fecalFile!);
      setState(() {
        _fecalResults = response;
        _isLoadingFecal = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Fecal analysis completed!'),
            backgroundColor: AppTheme.primaryGreen,
          ),
        );
      }
    } catch (e) {
      setState(() {
        _isLoadingFecal = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Analysis failed: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _downloadReport(String type, DiseaseResponse result) async {
    try {
      final disease = result.diseaseInfo;
      final confidencePercent = (result.confidence * 100).toStringAsFixed(1);
      final now = DateTime.now();
      final dateStr = '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';

      String reportContent = 'DISEASE DETECTION REPORT\n';
      reportContent += '================================\n\n';
      reportContent += 'Type: ${type == 'broiler' ? 'Broiler Disease Detection' : 'Fecal Analysis'}\n';
      reportContent += 'Date: ${now.toString()}\n\n';
      reportContent += 'DIAGNOSIS\n';
      reportContent += '---------\n';
      reportContent += 'Disease: ${disease.name}\n';
      if (disease.nameAr.isNotEmpty) {
        reportContent += '(${disease.nameAr})\n';
      }
      reportContent += 'Confidence: $confidencePercent%\n\n';

      if (disease.description.isNotEmpty) {
        reportContent += 'DESCRIPTION\n';
        reportContent += '-----------\n';
        reportContent += '${disease.description}\n';
        if (disease.descriptionAr.isNotEmpty) {
          reportContent += '${disease.descriptionAr}\n';
        }
        reportContent += '\n';
      }

      if (disease.symptoms.isNotEmpty) {
        reportContent += 'SYMPTOMS\n';
        reportContent += '--------\n';
        for (int i = 0; i < disease.symptoms.length; i++) {
          reportContent += '${i + 1}. ${disease.symptoms[i]}';
          if (i < disease.symptomsAr.length && disease.symptomsAr[i].isNotEmpty) {
            reportContent += ' (${disease.symptomsAr[i]})';
          }
          reportContent += '\n';
        }
        reportContent += '\n';
      }

      if (disease.treatment.isNotEmpty) {
        reportContent += 'RECOMMENDED TREATMENT\n';
        reportContent += '----------------------\n';
        for (int i = 0; i < disease.treatment.length; i++) {
          final treatment = disease.treatment[i];
          if (treatment is Map) {
            reportContent += '${i + 1}. ${treatment['name'] ?? 'Treatment'}\n';
            if (treatment['dose'] != null) {
              reportContent += '   Dose: ${treatment['dose']}\n';
            }
            if (treatment['method'] != null) {
              reportContent += '   Method: ${treatment['method']}\n';
            }
            if (treatment['duration'] != null) {
              reportContent += '   Duration: ${treatment['duration']}\n';
            }
            if (treatment['description'] != null) {
              reportContent += '   ${treatment['description']}\n';
            }
            if (i < disease.treatmentAr.length && disease.treatmentAr[i] is Map) {
              final ar = disease.treatmentAr[i] as Map;
              reportContent += '   (${ar['name'] ?? ''}';
              if (ar['dose'] != null) reportContent += ' - الجرعة: ${ar['dose']}';
              if (ar['method'] != null) reportContent += ' - طريقة: ${ar['method']}';
              if (ar['duration'] != null) reportContent += ' - المدة: ${ar['duration']}';
              if (ar['description'] != null) reportContent += ' - ${ar['description']}';
              reportContent += ')\n';
            }
          } else {
            reportContent += '${i + 1}. $treatment';
            if (i < disease.treatmentAr.length && disease.treatmentAr[i].toString().isNotEmpty) {
              reportContent += ' (${disease.treatmentAr[i]})';
            }
            reportContent += '\n';
          }
        }
        reportContent += '\n';
      }

      if (disease.prevention != null && disease.prevention!.isNotEmpty) {
        reportContent += 'PREVENTION MEASURES\n';
        reportContent += '------------------\n';
        for (int i = 0; i < disease.prevention!.length; i++) {
          reportContent += '${i + 1}. ${disease.prevention![i]}';
          if (disease.preventionAr != null &&
              i < disease.preventionAr!.length &&
              disease.preventionAr![i].isNotEmpty) {
            reportContent += ' (${disease.preventionAr![i]})';
          }
          reportContent += '\n';
        }
        reportContent += '\n';
      }

      // Add medication guidelines
      reportContent += '\n================================\n';
      reportContent += 'ملخص عام للجرعات والإدارة\n';
      reportContent += '================================\n\n';
      reportContent += 'قواعد عامة لإعطاء الأدوية:\n';
      reportContent += '- حساب الجرعة: بناءً على وزن الطيور أو كمية الماء المتوقع استهلاكها\n';
      reportContent += '- وقت الإعطاء: في الصباح الباكر مع الماء النظيف\n';
      reportContent += '- فترة العلاج: 3-7 أيام حسب شدة المرض\n';
      reportContent += '- فترة السحب: مراعاة فترة سحب الأدوية قبل الذبح\n\n';
      reportContent += 'بروتوكول الطوارئ:\n';
      reportContent += '- التشخيص المبكر: مراقبة الأعراض اليومية\n';
      reportContent += '- العزل الفوري: فصل الطيور المريضة\n';
      reportContent += '- العلاج الجماعي: إعطاء العلاج للقطيع كاملاً في الأمراض المعدية\n';
      reportContent += '- التطهير: تنظيف وتطهير الحظيرة والمعدات\n\n';
      reportContent += 'الوقاية خير من العلاج:\n';
      reportContent += '✅ برنامج تحصين منتظم\n';
      reportContent += '✅ نظافة وتطهير دوري\n';
      reportContent += '✅ تهوية جيدة وكثافة مناسبة\n';
      reportContent += '✅ تغذية متوازنة وماء نظيف\n';
      reportContent += '✅ إدارة الإجهاد وتجنب العوامل المسببة له\n\n';
      reportContent += '🚨 تحذيرات مهمة:\n';
      reportContent += '- استشارة البيطري: ضرورية قبل بدء أي برنامج علاجي\n';
      reportContent += '- الالتزام بالجرعات: تجنب زيادة الجرعات دون استشارة\n';
      reportContent += '- فترات السحب: ضرورية لمنع بقايا الأدوية في اللحم والبيض\n';
      reportContent += '- تسجيل العلاج: توثيق جميع العلاجات المستخدمة\n';
      reportContent += '- مراقبة الاستجابة: تقييم فعالية العلاج بعد 48-72 ساعة\n';

      // Save to file and share
      if (kIsWeb) {
        // On web, create a blob and download using dart:html directly
        final blob = html.Blob([reportContent.codeUnits]);
        final url = html.Url.createObjectUrlFromBlob(blob);
        final anchor = html.AnchorElement(href: url)
          ..setAttribute('download', '${type}_disease_report_$dateStr.txt')
          ..click();
        html.Url.revokeObjectUrl(url);
      } else {
        // On mobile, save to file using dart:io File
        // We'll use a workaround to avoid File constructor issues
        if (!kIsWeb) {
          final directory = await getApplicationDocumentsDirectory();
          final filePath = '${directory.path}/${type}_disease_report_$dateStr.txt';
          
          // Write file using dart:io File - create it using a helper
          // Since we're in !kIsWeb block, we can safely use dart:io
          // Write file using helper function that handles platform differences
          await _writeFileAndShare(filePath, reportContent, context);
        }
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Report downloaded successfully!'),
            backgroundColor: AppTheme.primaryGreen,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to download report: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }
}

