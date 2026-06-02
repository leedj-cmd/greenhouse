import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:team_plant_app/services/ai_service.dart';
import 'package:intl/intl.dart';

List<CameraDescription> _cameras = [];

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const PlantApp());
}

// 진단 기록 데이터 모델
class DetectionRecord {
  final String area;
  final String diseaseName;
  final String date;
  final String? imagePath;

  DetectionRecord({
    required this.area,
    required this.diseaseName,
    required this.date,
    this.imagePath,
  });
}

class PlantApp extends StatelessWidget {
  const PlantApp({super.key});

  Future<void> _initialize() async {
    try {
      await dotenv.load(fileName: ".env");
      _cameras = await availableCameras();
    } catch (e) {
      debugPrint("Initialization error: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Plant Monitor 4x4',
      theme: ThemeData(
        brightness: Brightness.light, // 스크린샷에 맞춰 밝은 테마로 변경 가능
        scaffoldBackgroundColor: const Color(0xFFF5F7F5),
        primaryColor: const Color(0xFF2E7D32),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF2E7D32),
          brightness: Brightness.light,
          surface: Colors.white,
        ),
        useMaterial3: true,
      ),
      home: FutureBuilder(
        future: _initialize(),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Scaffold(
              body: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    CircularProgressIndicator(color: Color(0xFF4CAF50)),
                    SizedBox(height: 20),
                    Text("시스템 초기화 중...", style: TextStyle(color: Colors.black54)),
                  ],
                ),
              ),
            );
          }
          return const MainNavigationScreen();
        },
      ),
    );
  }
}

class MainNavigationScreen extends StatefulWidget {
  const MainNavigationScreen({super.key});

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
  int _selectedIndex = 0;
  final List<DetectionRecord> _history = [];

  // 공통 상태 관리
  final List<bool> _diseaseDetected = List.generate(16, (_) => false);
  final List<String?> _diseaseNames = List.generate(16, (_) => null);

  void _addRecord(DetectionRecord record) {
    setState(() {
      _history.insert(0, record);
    });
  }

  @override
  Widget build(BuildContext context) {
    final List<Widget> screens = [
      PlantMonitorGridScreen(
        diseaseDetected: _diseaseDetected,
        diseaseNames: _diseaseNames,
        onRecordAdded: _addRecord,
      ),
      ImageHistoryView(history: _history),
    ];

    return Scaffold(
      body: IndexedStack(
        index: _selectedIndex,
        children: screens,
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (index) => setState(() => _selectedIndex = index),
        selectedItemColor: const Color(0xFF2E7D32),
        unselectedItemColor: Colors.grey,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.grid_view_rounded), label: 'Farm'),
          BottomNavigationBarItem(icon: Icon(Icons.image_outlined), label: 'Image'),
        ],
      ),
    );
  }
}

class PlantMonitorGridScreen extends StatefulWidget {
  final List<bool> diseaseDetected;
  final List<String?> diseaseNames;
  final Function(DetectionRecord) onRecordAdded;

  const PlantMonitorGridScreen({
    super.key,
    required this.diseaseDetected,
    required this.diseaseNames,
    required this.onRecordAdded,
  });

  @override
  State<PlantMonitorGridScreen> createState() => _PlantMonitorGridScreenState();
}

class _PlantMonitorGridScreenState extends State<PlantMonitorGridScreen> {
  CameraController? _controller;
  bool _isInitialized = false;
  bool _isDiagnosing = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _initializeCamera();
  }

  Future<void> _initializeCamera() async {
    try {
      if (_cameras.isEmpty) {
        setState(() {
          _errorMessage = "카메라를 찾을 수 없습니다.\n시뮬레이션 모드를 사용합니다.";
        });
        return;
      }

      _controller = CameraController(_cameras[0], ResolutionPreset.medium, enableAudio: false);
      await _controller!.initialize();

      if (!mounted) return;
      setState(() {
        _isInitialized = true;
        _errorMessage = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = "카메라 초기화 실패: $e";
      });
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  String _getAreaName(int index) {
    final String row = String.fromCharCode(65 + (index ~/ 4)); // A, B, C, D
    final int col = (index % 4) + 1;
    return '$row$col';
  }

  Future<void> _handleDiagnosis(int index) async {
    final bool isSimulation = _controller == null;
    if (!isSimulation && (!_isInitialized || _isDiagnosing)) return;

    setState(() => _isDiagnosing = true);

    try {
      Map<String, dynamic> result;
      String? imagePath;

      if (isSimulation) {
        await Future.delayed(const Duration(seconds: 1));
        final bool mockDisease = index == 1; // 스크린샷처럼 A2에서 질병 발생 시뮬레이션
        result = {
          'diseaseName': mockDisease ? 'RUST' : '정상',
        };
      } else {
        final XFile image = await _controller!.takePicture();
        imagePath = image.path;
        result = await AIService.diagnosePlant(image);
      }

      final String diseaseName = result['diseaseName'] ?? '알 수 없음';
      final bool hasDisease = !diseaseName.contains('정상') && 
                            !diseaseName.contains('건강') && 
                            !diseaseName.toLowerCase().contains('healthy');

      setState(() {
        widget.diseaseDetected[index] = hasDisease;
        widget.diseaseNames[index] = diseaseName;
        _isDiagnosing = false;
      });

      if (hasDisease) {
        widget.onRecordAdded(DetectionRecord(
          area: _getAreaName(index),
          diseaseName: diseaseName,
          date: DateFormat('yyyy-MM-dd').format(DateTime.now()),
          imagePath: imagePath,
        ));
      }
    } catch (e) {
      setState(() => _isDiagnosing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const Icon(Icons.eco, color: Color(0xFF2E7D32)),
            const SizedBox(width: 8),
            const Text('구역 현황', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF2E7D32))),
          ],
        ),
        backgroundColor: Colors.white,
        elevation: 0,
      ),
      body: Stack(
        children: [
          if (_errorMessage != null && !_isInitialized)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.videocam_off_outlined, color: Colors.orange, size: 48),
                    const SizedBox(height: 16),
                    Text(_errorMessage!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.black54)),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      onPressed: () {
                        setState(() {
                          _errorMessage = null;
                          _controller = null; // 시뮬레이션 모드 강제 전환
                        });
                      },
                      child: const Text("시뮬레이션 모드로 계속"),
                    ),
                  ],
                ),
              ),
            )
          else
            GridView.builder(
              padding: const EdgeInsets.all(16),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 4,
              childAspectRatio: 0.6,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
            ),
            itemCount: 16,
            itemBuilder: (context, index) {
              final String areaName = _getAreaName(index);
              final bool isAlert = widget.diseaseDetected[index];

              return GestureDetector(
                onTap: () => _handleDiagnosis(index),
                child: Container(
                  decoration: BoxDecoration(
                    color: isAlert ? const Color(0xFFFFEBEE) : const Color(0xFFE8F5E9),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      if (isAlert)
                        const Icon(Icons.warning_rounded, color: Colors.red, size: 40)
                      else
                        const SizedBox(height: 40),
                      const SizedBox(height: 12),
                      Text(areaName, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.circle, color: isAlert ? Colors.red : Colors.green, size: 8),
                          const SizedBox(width: 4),
                          Text(
                            isAlert ? '질병 감지' : '정상',
                            style: TextStyle(
                              color: isAlert ? Colors.red : Colors.green,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
          if (_isDiagnosing)
            Container(
              color: Colors.black26,
              child: const Center(child: CircularProgressIndicator(color: Colors.green)),
            ),
        ],
      ),
    );
  }
}

class ImageHistoryView extends StatelessWidget {
  final List<DetectionRecord> history;

  const ImageHistoryView({super.key, required this.history});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const Text('🖼️ ', style: TextStyle(fontSize: 20)),
            const Text('사진 기록', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF2E7D32))),
          ],
        ),
        backgroundColor: Colors.white,
        elevation: 0,
      ),
      body: history.isEmpty
          ? const Center(child: Text("기록된 질병 사진이 없습니다.", style: TextStyle(color: Colors.grey)))
          : GridView.builder(
              padding: const EdgeInsets.all(16),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                crossAxisSpacing: 16,
                mainAxisSpacing: 16,
                childAspectRatio: 0.85,
              ),
              itemCount: history.length,
              itemBuilder: (context, index) {
                final record = history[index];
                return Container(
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(8),
                    boxShadow: [
                      BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 4, offset: const Offset(0, 2)),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Expanded(
                        child: Stack(
                          children: [
                            Container(
                              decoration: BoxDecoration(
                                color: const Color(0xFF00E676).withOpacity(0.6),
                                borderRadius: const BorderRadius.vertical(top: Radius.circular(8)),
                              ),
                              child: record.imagePath != null
                                  ? Image.file(File(record.imagePath!), fit: BoxFit.cover, width: double.infinity)
                                  : const Center(child: Icon(Icons.grid_on, color: Colors.white70, size: 40)),
                            ),
                            Positioned(
                              top: 8,
                              left: 8,
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: Colors.red,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  record.diseaseName,
                                  style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.all(8.0),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(record.area, style: const TextStyle(fontWeight: FontWeight.bold)),
                            Text(record.date, style: const TextStyle(color: Colors.grey, fontSize: 10)),
                          ],
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
    );
  }
}
