const express = require('express');
const router  = express.Router();
const db      = require('../db');

// GET /api/v1/fields
router.get('/', async (req, res, next) => {
    try {
        const result = await db.query(
            `SELECT id AS field_id, name AS field_name, location, status
             FROM fields
             ORDER BY id ASC`
        );
        return res.json({ data: result.rows });
    } catch (err) {
        next(err);
    }
});

module.exports = router;
