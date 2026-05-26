import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:team_plant_app/services/ai_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: ".env");
  runApp(const PlantApp());
}

class PlantApp extends StatelessWidget {
  const PlantApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Dr. Plant',
      theme: ThemeData(
        primaryColor: const Color(0xFF4C7B53),
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF4C7B53)),
        scaffoldBackgroundColor: const Color(0xFFF9F9F9),
        useMaterial3: true,
      ),
      home: const PlantHomeScreen(),
    );
  }
}

class PlantHomeScreen extends StatefulWidget {
  const PlantHomeScreen({super.key});

  @override
  State<PlantHomeScreen> createState() => _PlantHomeScreenState();
}

class _PlantHomeScreenState extends State<PlantHomeScreen> {
  File? _image;
  bool _isAnalyzing = false;
  final ImagePicker _picker = ImagePicker();

  Future<void> _pickImage(ImageSource source) async {
    final XFile? pickedFile = await _picker.pickImage(source: source);

    if (pickedFile != null) {
      setState(() {
        _image = File(pickedFile.path);
      });
    }
  }

  void _startDiagnosis() async {
    if (_image == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('식물 잎 사진을 먼저 선택해주세요!')),
      );
      return;
    }

    setState(() {
      _isAnalyzing = true;
    });

    try {
      final result = await AIService.diagnosePlant(_image!);

      if (!mounted) return;
      setState(() {
        _isAnalyzing = false;
      });

      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (context) => DiagnosisResultScreen(
            image: _image!,
            plantName: result['plantName'],
            diseaseName: result['diseaseName'],
            symptoms: result['symptoms'],
            feedback: List<String>.from(result['feedback']),
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isAnalyzing = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('진단 중 오류가 발생했습니다: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('닥터 플랜트 🌿', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white)),
        backgroundColor: const Color(0xFF4C7B53),
        centerTitle: true,
      ),
      body: Center(
        child: _isAnalyzing
            ? const Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(color: Color(0xFF4C7B53)),
                  SizedBox(height: 24),
                  Text('AI가 식물 질병을 정밀 분석 중입니다...', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                  SizedBox(height: 8),
                  Text('잠시만 기다려주세요.', style: TextStyle(fontSize: 14, color: Colors.grey)),
                ],
              )
            : SingleChildScrollView(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    GestureDetector(
                      onTap: () {
                        showModalBottomSheet(
                          context: context,
                          builder: (context) => SafeArea(
                            child: Wrap(
                              children: [
                                ListTile(
                                  leading: const Icon(Icons.photo_library),
                                  title: const Text('갤러리에서 선택'),
                                  onTap: () {
                                    _pickImage(ImageSource.gallery);
                                    Navigator.pop(context);
                                  },
                                ),
                                ListTile(
                                  leading: const Icon(Icons.camera_alt),
                                  title: const Text('사진 촬영하기'),
                                  onTap: () {
                                    _pickImage(ImageSource.camera);
                                    Navigator.pop(context);
                                  },
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                      child: Container(
                        width: double.infinity,
                        height: 300,
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(24),
                          border: Border.all(color: Color(0xFF4C7B53).withOpacity(0.3), width: 2),
                          boxShadow: [
                            BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 15, offset: const Offset(0, 8)),
                          ],
                        ),
                        child: _image != null
                            ? ClipRRect(
                                borderRadius: BorderRadius.circular(22),
                                child: Image.file(_image!, fit: BoxFit.cover),
                              )
                            : const Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.add_a_photo_rounded, size: 80, color: Color(0xFF4C7B53)),
                                  SizedBox(height: 16),
                                  Text('진단할 잎 사진을 올려주세요', style: TextStyle(fontSize: 16, color: Colors.grey, fontWeight: FontWeight.w500)),
                                ],
                              ),
                      ),
                    ),
                    const SizedBox(height: 48),
                    SizedBox(
                      width: double.infinity,
                      height: 56,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF4C7B53),
                          foregroundColor: Colors.white,
                          elevation: 0,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        ),
                        onPressed: _startDiagnosis,
                        child: const Text('진단 시작하기 🚀', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                      ),
                    ),
                    if (_image != null)
                      TextButton(
                        onPressed: () => setState(() => _image = null),
                        child: const Text('사진 다시 선택하기', style: TextStyle(color: Colors.grey)),
                      ),
                  ],
                ),
              ),
      ),
    );
  }
}

class DiagnosisResultScreen extends StatelessWidget {
  final File image;
  final String plantName;
  final String diseaseName;
  final String symptoms;
  final List<String> feedback;

  const DiagnosisResultScreen({
    super.key,
    required this.image,
    required this.plantName,
    required this.diseaseName,
    required this.symptoms,
    required this.feedback,
  });

  @override
  Widget build(BuildContext context) {
    final bool isHealthy = diseaseName.contains('건강') || diseaseName.toLowerCase() == 'healthy';

    return Scaffold(
      appBar: AppBar(
        title: const Text('진단 결과', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFF4C7B53),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: Image.file(image, height: 200, width: double.infinity, fit: BoxFit.cover),
              ),
            ),
            const SizedBox(height: 24),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 20, offset: const Offset(0, 4))],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(plantName, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: isHealthy ? Colors.green.withOpacity(0.1) : Colors.red.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          diseaseName,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: isHealthy ? Colors.green : Colors.redAccent,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const Divider(height: 32),
                  const Text('🧐 주요 증상', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Text(symptoms, style: const TextStyle(fontSize: 15, color: Colors.black87, height: 1.5)),
                ],
              ),
            ),
            const SizedBox(height: 32),
            const Text('👨‍🌾 지금 당장 해주세요! (피드백)', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            ...feedback.asMap().entries.map((entry) {
              return _buildActionStep((entry.key + 1).toString(), entry.value);
            }).toList(),
            const SizedBox(height: 40),
            SizedBox(
              width: double.infinity,
              height: 56,
              child: OutlinedButton(
                style: OutlinedButton.styleFrom(
                  side: BorderSide(color: Color(0xFF4C7B53).withOpacity(0.5)),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
                onPressed: () => Navigator.pop(context),
                child: const Text('다시 진단하기', style: TextStyle(fontSize: 16, color: Color(0xFF4C7B53), fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActionStep(String step, String description) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 28,
            height: 28,
            alignment: Alignment.center,
            decoration: const BoxDecoration(
              color: Color(0xFF4C7B53),
              shape: BoxShape.circle,
            ),
            child: Text(step, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold)),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Text(description, style: const TextStyle(fontSize: 15, color: Colors.black87, height: 1.4)),
          ),
        ],
      ),
    );
  }
}
