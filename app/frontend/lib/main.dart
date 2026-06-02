import 'dart:async';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:team_plant_app/services/ai_service.dart';

List<CameraDescription> _cameras = [];

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const PlantApp());
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
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0A0F0A),
        primaryColor: const Color(0xFF2E7D32),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF2E7D32),
          brightness: Brightness.dark,
          surface: const Color(0xFF161D17),
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
                    Text("모니터링 시스템 준비 중...", style: TextStyle(color: Colors.white70)),
                  ],
                ),
              ),
            );
          }
          return const PlantMonitorGridScreen();
        },
      ),
    );
  }
}

class PlantMonitorGridScreen extends StatefulWidget {
  const PlantMonitorGridScreen({super.key});

  @override
  State<PlantMonitorGridScreen> createState() => _PlantMonitorGridScreenState();
}

class _PlantMonitorGridScreenState extends State<PlantMonitorGridScreen> {
  CameraController? _controller;
  bool _isInitialized = false;
  bool _isDiagnosing = false;
  String? _errorMessage;

  // 각 칸의 상태 관리 (16개)
  final List<bool> _diseaseDetected = List.generate(16, (_) => false);
  final List<String?> _plantNames = List.generate(16, (_) => null);
  final List<String?> _diseaseNames = List.generate(16, (_) => null);

  @override
  void initState() {
    super.initState();
    _initializeCamera();
  }

  Future<void> _initializeCamera() async {
    try {
      if (_cameras.isEmpty) {
        setState(() {
          _errorMessage = "카메라를 찾을 수 없습니다.\n시스템 설정을 확인하거나 시뮬레이션 모드를 사용하세요.";
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

  Future<void> _handleDiagnosis(int index) async {
    // 시뮬레이션 모드 또는 일반 모드 체크
    final bool isSimulation = _controller == null;

    if (!isSimulation && (!_isInitialized || _isDiagnosing)) return;

    setState(() {
      _isDiagnosing = true;
    });

    try {
      Map<String, dynamic> result;

      if (isSimulation) {
        // 시뮬레이션 모드: 1초 대기 후 랜덤 결과 생성
        await Future.delayed(const Duration(seconds: 1));
        final bool mockDisease = index % 3 == 0; // 3의 배수 칸은 병이 있는 것으로 시뮬레이션
        result = {
          'plantName': '시뮬레이션 식물',
          'diseaseName': mockDisease ? '잎곰팡이병 (가상)' : '건강함',
        };
      } else {
        // 일반 모드: 실제 사진 캡처 및 AI 진단
        final XFile image = await _controller!.takePicture();
        result = await AIService.diagnosePlant(image);
      }

      final String diseaseName = result['diseaseName'] ?? '알 수 없음';
      final bool hasDisease = !diseaseName.contains('건강') && !diseaseName.toLowerCase().contains('healthy');

      setState(() {
        _diseaseDetected[index] = hasDisease;
        _plantNames[index] = result['plantName'];
        _diseaseNames[index] = diseaseName;
        _isDiagnosing = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('CAM ${index + 1} 진단 완료: $diseaseName'),
            backgroundColor: hasDisease ? Colors.redAccent : const Color(0xFF2E7D32),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            duration: const Duration(seconds: 2),
          ),
        );
      }
    } catch (e) {
      setState(() {
        _isDiagnosing = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('진단 오류: $e'),
            backgroundColor: Colors.red.shade800,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Column(
          children: [
            Text('Smart Monitoring System',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white, letterSpacing: 0.5)),
            Text('비닐하우스 스마트 모니터링 (4x4)',
                style: TextStyle(fontSize: 12, color: Colors.white70, fontWeight: FontWeight.normal)),
          ],
        ),
        backgroundColor: const Color(0xFF121A13),
        elevation: 0,
        centerTitle: true,
        toolbarHeight: 70,
      ),
      body: Stack(
        children: [
          if (_isInitialized || _controller == null && _errorMessage == null)
            GridView.builder(
              padding: const EdgeInsets.all(12),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 4,
                childAspectRatio: 0.95,
                crossAxisSpacing: 10,
                mainAxisSpacing: 10,
              ),
              itemCount: 16,
              itemBuilder: (context, index) {
                return GestureDetector(
                  onTap: () => _handleDiagnosis(index),
                  child: CameraTile(
                    controller: _controller,
                    isAlert: _diseaseDetected[index],
                    index: index,
                    plantName: _plantNames[index],
                    diseaseName: _diseaseNames[index],
                  ),
                );
              },
            )
          else if (_errorMessage != null)
            Center(
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 24),
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: const Color(0xFF161D17),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.white10),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.videocam_off_outlined, color: Colors.orangeAccent, size: 64),
                    const SizedBox(height: 20),
                    Text(_errorMessage!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: Colors.white, fontSize: 16, height: 1.5)),
                    const SizedBox(height: 32),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF2E7D32),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        elevation: 4,
                      ),
                      onPressed: () {
                        setState(() {
                          _isInitialized = true;
                          _errorMessage = null;
                          _controller = null; // 시뮬레이션 모드
                        });
                      },
                      child: const Text("시뮬레이션 모드 시작", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                    ),
                    const SizedBox(height: 16),
                    TextButton(
                      onPressed: _initializeCamera,
                      child: const Text("카메라 다시 연결", style: TextStyle(color: Colors.white54)),
                    ),
                  ],
                ),
              ),
            )
          else
            const Center(child: CircularProgressIndicator(color: Color(0xFF4CAF50))),

          if (_isDiagnosing)
            Container(
              color: Colors.black.withOpacity(0.7),
              child: Center(
                child: Container(
                  padding: const EdgeInsets.all(32),
                  decoration: BoxDecoration(
                      color: const Color(0xFF161D17),
                      borderRadius: BorderRadius.circular(20),
                      boxShadow: [
                        BoxShadow(color: Colors.black.withOpacity(0.5), blurRadius: 20, spreadRadius: 5)
                      ]
                  ),
                  child: const Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      CircularProgressIndicator(color: Color(0xFF4CAF50), strokeWidth: 3),
                      SizedBox(height: 24),
                      Text('AI 정밀 진단 중...',
                          style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                      SizedBox(height: 8),
                      Text('이미지를 분석하고 있습니다', style: TextStyle(color: Colors.white54, fontSize: 14)),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class CameraTile extends StatefulWidget {
  final CameraController? controller;
  final bool isAlert;
  final int index;
  final String? plantName;
  final String? diseaseName;

  const CameraTile({
    super.key,
    this.controller,
    required this.isAlert,
    required this.index,
    this.plantName,
    this.diseaseName,
  });

  @override
  State<CameraTile> createState() => _CameraTileState();
}

class _CameraTileState extends State<CameraTile> with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _glowAnimation;

  final List<String> _leafEmojis = ['🌿', '🍃', '🌱', '🪴', '🍀', '☘️', '🎋', '🍃'];

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    );
    _glowAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );

    if (widget.isAlert) {
      _animationController.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(CameraTile oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isAlert && !oldWidget.isAlert) {
      _animationController.repeat(reverse: true);
    } else if (!widget.isAlert && oldWidget.isAlert) {
      _animationController.stop();
      _animationController.reset();
    }
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final String leafEmoji = _leafEmojis[widget.index % _leafEmojis.length];

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF1E2620),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: widget.isAlert ? Colors.red.withOpacity(0.5) : Colors.white.withOpacity(0.05),
          width: 1.5,
        ),
        boxShadow: [
          if (widget.isAlert)
            BoxShadow(
              color: Colors.red.withOpacity(0.2 * _animationController.value),
              blurRadius: 8,
              spreadRadius: 2,
            )
          else
            BoxShadow(
              color: Colors.black.withOpacity(0.2),
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(15),
        child: Stack(
          fit: StackFit.expand,
          children: [
            // 배경: 카메라 미리보기 또는 시뮬레이션 아이콘
            widget.controller != null && widget.controller!.value.isInitialized
                ? Center(
              child: FittedBox(
                fit: BoxFit.cover,
                child: SizedBox(
                  width: 100,
                  height: 100,
                  child: CameraPreview(widget.controller!),
                ),
              ),
            )
                : Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(leafEmoji, style: const TextStyle(fontSize: 32)),
                  const SizedBox(height: 4),
                  const Icon(Icons.sensors, color: Colors.white10, size: 12),
                ],
              ),
            ),

            // 상단 레이블 (카메라 번호)
            Positioned(
              top: 8,
              left: 8,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                decoration: BoxDecoration(
                  color: Colors.black.withOpacity(0.4),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 4,
                      height: 4,
                      decoration: BoxDecoration(
                        color: widget.isAlert ? Colors.red : Colors.greenAccent,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'CH ${widget.index + 1}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // 진단 결과 표시
            if (widget.diseaseName != null)
              Positioned(
                bottom: 0,
                left: 0,
                right: 0,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.bottomCenter,
                      end: Alignment.topCenter,
                      colors: widget.isAlert
                          ? [Colors.red.withOpacity(0.9), Colors.red.withOpacity(0.4)]
                          : [const Color(0xFF2E7D32).withOpacity(0.9), const Color(0xFF2E7D32).withOpacity(0.4)],
                    ),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        widget.isAlert ? '⚠ 위험' : '✓ 건강',
                        style: const TextStyle(color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold),
                      ),
                      Text(
                        widget.diseaseName!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
              ),

            // 질병 발생 시 빨간색 오버레이 (맥동 효과)
            if (widget.isAlert)
              AnimatedBuilder(
                animation: _glowAnimation,
                builder: (context, child) {
                  return Container(
                    decoration: BoxDecoration(
                      border: Border.all(
                        color: Colors.red.withOpacity(0.3 * _glowAnimation.value),
                        width: 4,
                      ),
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }
}