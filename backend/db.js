const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
    host:     process.env.DB_HOST     || 'localhost',
    port:     parseInt(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME     || 'greenhouse_db',
    user:     process.env.DB_USER     || 'postgres',
    password: process.env.DB_PASSWORD || '',
});

// 서버 시작 시 DB 연결 확인
pool.connect((err, client, release) => {
    if (err) {
        console.error('❌ DB 연결 실패:', err.message);
    } else {
        console.log('✅ PostgreSQL 연결 성공');
        release();
    }
});

module.exports = pool;
