const express = require('express');
const router  = express.Router();
const db      = require('../db');

// GET /api/v1/history
router.get('/', async (req, res, next) => {
    const {
        field_id,
        limit        = 20,
        offset       = 0,
        disease_only = false,
    } = req.query;

    // limit 최대 100 제한
    const safeLimit  = Math.min(parseInt(limit)  || 20,  100);
    const safeOffset = Math.max(parseInt(offset) || 0,   0);
    const diseaseOnly = disease_only === 'true';

    try {
        const conditions = [];
        const params     = [];
        let   paramIndex = 1;

        if (field_id) {
            conditions.push(`field_id = $${paramIndex++}`);
            params.push(parseInt(field_id));
        }
        if (diseaseOnly) {
            conditions.push(`disease_detected = TRUE`);
        }

        const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

        // 전체 건수 조회
        const countResult = await db.query(
            `SELECT COUNT(*) FROM analysis_results ${whereClause}`,
            params
        );
        const total = parseInt(countResult.rows[0].count);

        // 데이터 조회
        const dataResult = await db.query(
            `SELECT
                id              AS analysis_id,
                field_id,
                disease_detected,
                disease_type,
                confidence,
                image_path      AS image_url,
                timestamp
             FROM analysis_results
             ${whereClause}
             ORDER BY timestamp DESC
             LIMIT $${paramIndex++} OFFSET $${paramIndex++}`,
            [...params, safeLimit, safeOffset]
        );

        return res.json({
            data:   dataResult.rows,
            total,
            limit:  safeLimit,
            offset: safeOffset,
        });

    } catch (err) {
        next(err);
    }
});

module.exports = router;
