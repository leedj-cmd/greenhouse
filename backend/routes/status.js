const express = require('express');
const router  = express.Router();
const db      = require('../db');

// GET /api/v1/status/:field_id
router.get('/:field_id', async (req, res, next) => {
    const fieldId = parseInt(req.params.field_id);

    if (isNaN(fieldId) || fieldId < 1 || fieldId > 5) {
        return res.status(400).json({ error: '유효하지 않은 field_id입니다. (1~5)', code: 'INVALID_FIELD_ID' });
    }

    try {
        // 밭 정보 + 최신 분석 결과 한 번에 조회 (DB 뷰 활용)
        const result = await db.query(
            `SELECT * FROM v_field_latest_status WHERE field_id = $1`,
            [fieldId]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({ error: '해당 밭을 찾을 수 없습니다.', code: 'FIELD_NOT_FOUND' });
        }

        const row = result.rows[0];

        return res.json({
            field_id:   row.field_id,
            field_name: row.field_name,
            location:   row.location,
            status:     row.field_status,
            latest_analysis: row.latest_analysis_id ? {
                analysis_id:      row.latest_analysis_id,
                disease_detected: row.disease_detected,
                disease_type:     row.disease_type,
                confidence:       row.confidence,
                timestamp:        row.last_analyzed_at,
            } : null,
        });

    } catch (err) {
        next(err);
    }
});

module.exports = router;
