const express = require('express');
const router  = express.Router();
const path    = require('path');
const fs      = require('fs');
const db      = require('../db');

// 유효한 disease_type 목록
const DISEASE_TYPES = ['powdery_mildew', 'leaf_spot', 'blight', 'gray_mold', 'mosaic_virus'];

// disease_type → 한국어 메시지
const DISEASE_MESSAGES = {
    powdery_mildew: '흰가루병이 감지되었습니다',
    leaf_spot:      '점무늬병이 감지되었습니다',
    blight:         '역병이 감지되었습니다',
    gray_mold:      '잿빛곰팡이병이 감지되었습니다',
    mosaic_virus:   '모자이크바이러스가 감지되었습니다',
};

// confidence 기준으로 field status 결정
function getFieldStatus(diseaseDetected, confidence) {
    if (!diseaseDetected) return 'healthy';
    if (confidence >= 0.9)  return 'critical';
    return 'warning';
}

// POST /api/v1/analyze
router.post('/', async (req, res, next) => {
    const { field_id, image_base64, timestamp } = req.body;

    // ── 입력 검증 ──────────────────────────────────
    if (!field_id) {
        return res.status(400).json({ error: 'field_id는 필수입니다.', code: 'MISSING_FIELD_ID' });
    }
    if (!image_base64) {
        return res.status(400).json({ error: 'image_base64는 필수입니다.', code: 'MISSING_IMAGE' });
    }
    if (field_id < 1 || field_id > 5) {
        return res.status(400).json({ error: '유효하지 않은 field_id입니다. (1~5)', code: 'INVALID_FIELD_ID' });
    }

    try {
        // ── 이미지 저장 ────────────────────────────────
        const uploadsDir = path.join(__dirname, '..', 'uploads');
        if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir, { recursive: true });

        const { v4: uuidv4 } = require('uuid');
        const imageId    = uuidv4();
        const imagePath  = path.join(uploadsDir, `${imageId}.jpg`);
        const imageUrl   = `/images/${imageId}.jpg`;

        const base64Data = image_base64.replace(/^data:image\/\w+;base64,/, '');
        fs.writeFileSync(imagePath, Buffer.from(base64Data, 'base64'));

        // ── AI 분석 (Mock — 실제 모델 연동 시 교체) ────────
        // TODO: TensorFlow Lite 모델 또는 Python AI 서버 호출로 교체
        const mockResult = mockAnalyze();

        const analysisTimestamp = timestamp || new Date().toISOString();

        // ── DB 저장: analysis_results ──────────────────
        const insertAnalysis = `
            INSERT INTO analysis_results
                (field_id, image_path, disease_detected, disease_type, confidence, raw_output, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        `;
        const analysisResult = await db.query(insertAnalysis, [
            field_id,
            imageUrl,
            mockResult.disease_detected,
            mockResult.disease_type,
            mockResult.confidence,
            JSON.stringify(mockResult.raw_output),
            analysisTimestamp,
        ]);
        const analysisId = analysisResult.rows[0].id;

        // ── DB 업데이트: fields 상태 갱신 ──────────────
        const newStatus = getFieldStatus(mockResult.disease_detected, mockResult.confidence);
        await db.query(
            'UPDATE fields SET status = $1 WHERE id = $2',
            [newStatus, field_id]
        );

        // ── 질병 감지 시 알림 생성 ──────────────────────
        if (mockResult.disease_detected) {
            const message = DISEASE_MESSAGES[mockResult.disease_type] || '질병이 감지되었습니다';
            await db.query(
                'INSERT INTO notifications (field_id, analysis_id, message) VALUES ($1, $2, $3)',
                [field_id, analysisId, message]
            );
        }

        // ── 응답 ───────────────────────────────────────
        return res.json({
            analysis_id:      analysisId,
            field_id:         parseInt(field_id),
            disease_detected: mockResult.disease_detected,
            disease_type:     mockResult.disease_type,
            confidence:       mockResult.confidence,
            message:          mockResult.disease_detected
                                  ? (DISEASE_MESSAGES[mockResult.disease_type] || '질병이 감지되었습니다')
                                  : '정상입니다',
            timestamp:        analysisTimestamp,
        });

    } catch (err) {
        next(err);
    }
});

// ── Mock 분석 함수 ─────────────────────────────────────
// 실제 AI 모델 연동 전까지 랜덤 결과를 반환합니다.
// ML 팀이 모델을 완성하면 이 함수를 Python AI 서버 호출로 교체하세요.
function mockAnalyze() {
    const diseaseDetected = Math.random() > 0.5;
    const diseaseType     = diseaseDetected
        ? DISEASE_TYPES[Math.floor(Math.random() * DISEASE_TYPES.length)]
        : null;
    const confidence      = parseFloat((Math.random() * 0.3 + 0.7).toFixed(2)); // 0.70 ~ 1.00

    return {
        disease_detected: diseaseDetected,
        disease_type:     diseaseType,
        confidence,
        raw_output: { mock: true, scores: { disease: confidence, healthy: 1 - confidence } },
    };
}

module.exports = router;
