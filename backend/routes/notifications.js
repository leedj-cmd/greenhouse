const express = require('express');
const router  = express.Router();
const db      = require('../db');

// PATCH /api/v1/notifications/:id/read
router.patch('/:id/read', async (req, res, next) => {
    const { id } = req.params;

    try {
        const result = await db.query(
            `UPDATE notifications
             SET read_at = CURRENT_TIMESTAMP
             WHERE id = $1 AND read_at IS NULL
             RETURNING id AS notification_id, read_at`,
            [id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                error: '알림을 찾을 수 없거나 이미 읽음 처리되었습니다.',
                code: 'NOTIFICATION_NOT_FOUND',
            });
        }

        return res.json(result.rows[0]);

    } catch (err) {
        next(err);
    }
});

module.exports = router;
