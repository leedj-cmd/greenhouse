import 'dart:io';
import 'dart:convert';
import 'package:google_generative_ai/google_generative_ai.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class AIService {
  static final String _apiKey = dotenv.env['GEMINI_API_KEY'] ?? '';

  static Future<Map<String, dynamic>> diagnosePlant(File imageFile) async {
    if (_apiKey.isEmpty) {
      throw Exception('API Key is missing. Please add GEMINI_API_KEY to your .env file.');
    }

    final model = GenerativeModel(
      model: 'gemini-1.5-flash',
      apiKey: _apiKey,
    );

    final imageBytes = await imageFile.readAsBytes();
    final content = [
      Content.multi([
        TextPart('''
You are a plant pathology expert. Analyze the provided image of a plant leaf and provide a diagnosis in Korean.
Identify the following:
1. Plant Name (식물 이름)
2. Disease Name (병 이름 - if healthy, say "건강함")
3. Symptoms (증상 - if healthy, describe how it looks healthy)
4. Feedback/Action (지금 당장 해야할 피드백 - at least 3 steps)

Target plants include Apple, Corn, Potato, Tomato, Pepper as mentioned in our service planning.

Return the result in JSON format like this:
{
  "plantName": "...",
  "diseaseName": "...",
  "symptoms": "...",
  "feedback": ["step1", "step2", "step3"]
}
'''),
        DataPart('image/jpeg', imageBytes),
      ])
    ];

    try {
      final response = await model.generateContent(content);
      final text = response.text;
      
      if (text == null) throw Exception('Empty response from AI');

      // Extract JSON from response (sometimes Gemini wraps it in markdown)
      String jsonString = text.trim();
      if (jsonString.contains('```json')) {
        jsonString = jsonString.split('```json')[1].split('```')[0].trim();
      } else if (jsonString.contains('```')) {
        jsonString = jsonString.split('```')[1].split('```')[0].trim();
      }
      
      return jsonDecode(jsonString);
    } catch (e) {
      print('AI Diagnosis Error: $e');
      rethrow;
    }
  }
}
