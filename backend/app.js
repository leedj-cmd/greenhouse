require('dotenv').config();
const express = require('express');
const cors    = require('cors');
const path    = require('path');

const analyzeRouter       = require('./routes/analyze');
const historyRouter       = require('./routes/history');
const statusRouter        = require('./routes/status');
const fieldsRouter        = require('./routes/fields');
const notificationsRouter = require('./routes/notifications');

const app  = express();
const PORT = process.env.PORT || 3000;

// ── 미들웨어 ──────────────────────────────────────────
app.use(cors());
app.use(express.json({ limit: '10mb' }));   // Base64 이미지 수신을 위해 limit 증가
app.use(express.urlencoded({ extended: true }));

// 업로드된 이미지 정적 서빙
app.use('/images', express.static(path.join(__dirname, 'uploads')));

// ── 라우터 ──────────────────────────────────────────
app.use('/api/v1/analyze',       analyzeRouter);
app.use('/api/v1/history',       historyRouter);
app.use('/api/v1/status',        statusRouter);
app.use('/api/v1/fields',        fieldsRouter);
app.use('/api/v1/notifications', notificationsRouter);

// ── 헬스체크 ─────────────────────────────────────────
app.get('/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// ── 404 처리 ─────────────────────────────────────────
app.use((req, res) => {
    res.status(404).json({ error: '요청한 경로를 찾을 수 없습니다.', code: 'NOT_FOUND' });
});

// ── 전역 에러 핸들러 ──────────────────────────────────
app.use((err, req, res, next) => {
    console.error('서버 에러:', err);
    res.status(500).json({ error: '서버 내부 오류가 발생했습니다.', code: 'INTERNAL_ERROR' });
});

// ── 서버 시작 ────────────────────────────────────────
app.listen(PORT, () => {
    console.log(`🚀 서버 실행 중: http://localhost:${PORT}`);
    console.log(`📋 헬스체크: http://localhost:${PORT}/health`);
});
