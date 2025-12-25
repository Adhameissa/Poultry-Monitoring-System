class DiseaseInfo {
  final String name;
  final String nameAr;
  final String description;
  final String descriptionAr;
  final List<String> symptoms;
  final List<String> symptomsAr;
  final List<dynamic> treatment;
  final List<dynamic> treatmentAr;
  final List<String>? prevention;
  final List<String>? preventionAr;
  final String? causativeAgent;
  final String? causativeAgentAr;
  final String? ageAtRisk;
  final String? ageAtRiskAr;
  final String? lesions;
  final String? lesionsAr;
  final List<String>? infectionSources;
  final List<String>? infectionSourcesAr;
  final String? droppings;
  final String? droppingsAr;

  DiseaseInfo({
    required this.name,
    required this.nameAr,
    required this.description,
    required this.descriptionAr,
    required this.symptoms,
    required this.symptomsAr,
    required this.treatment,
    required this.treatmentAr,
    this.prevention,
    this.preventionAr,
    this.causativeAgent,
    this.causativeAgentAr,
    this.ageAtRisk,
    this.ageAtRiskAr,
    this.lesions,
    this.lesionsAr,
    this.infectionSources,
    this.infectionSourcesAr,
    this.droppings,
    this.droppingsAr,
  });

  factory DiseaseInfo.fromJson(Map<String, dynamic> json) {
    return DiseaseInfo(
      name: json['diagnosis'] ?? '',
      nameAr: json['diagnosis_ar'] ?? '',
      description: json['description'] ?? '',
      descriptionAr: json['description_ar'] ?? '',
      symptoms: List<String>.from(json['symptoms'] ?? []),
      symptomsAr: List<String>.from(json['symptoms_ar'] ?? []),
      treatment: json['treatment'] ?? [],
      treatmentAr: json['treatment_ar'] ?? [],
      prevention: json['prevention'] != null ? List<String>.from(json['prevention']) : null,
      preventionAr: json['prevention_ar'] != null ? List<String>.from(json['prevention_ar']) : null,
      causativeAgent: json['causative_agent'],
      causativeAgentAr: json['causative_agent_ar'],
      ageAtRisk: json['age_at_risk'],
      ageAtRiskAr: json['age_at_risk_ar'],
      lesions: json['lesions'],
      lesionsAr: json['lesions_ar'],
      infectionSources: json['infection_sources'] != null ? List<String>.from(json['infection_sources']) : null,
      infectionSourcesAr: json['infection_sources_ar'] != null ? List<String>.from(json['infection_sources_ar']) : null,
      droppings: json['droppings'],
      droppingsAr: json['droppings_ar'],
    );
  }
}

class DiseaseResponse {
  final bool success;
  final DiseaseInfo diseaseInfo;
  final double confidence;
  final String? annotatedImage;
  final Map<String, double>? allProbabilities;
  final String? message;

  DiseaseResponse({
    required this.success,
    required this.diseaseInfo,
    required this.confidence,
    this.annotatedImage,
    this.allProbabilities,
    this.message,
  });

  factory DiseaseResponse.fromJson(Map<String, dynamic> json) {
    return DiseaseResponse(
      success: json['success'] ?? false,
      diseaseInfo: DiseaseInfo.fromJson(json),
      confidence: (json['confidence'] ?? 0.0).toDouble(),
      annotatedImage: json['annotated_image'],
      allProbabilities: json['all_probabilities'] != null
          ? Map<String, double>.from(
              (json['all_probabilities'] as Map).map(
                (key, value) => MapEntry(key, (value as num).toDouble()),
              ),
            )
          : null,
      message: json['message'],
    );
  }
}

